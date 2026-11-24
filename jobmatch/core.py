import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class Job:
    company: str
    title: str
    region: str
    mode: str
    description: str


@dataclass(frozen=True)
class Profile:
    skills: tuple[str, ...]
    region: str
    remote_only: bool


def norm(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def collect(paths: list[Path]) -> list[Job]:
    if len(paths) > 50:
        raise ValueError("at most 50 snapshots per run")
    jobs: dict[tuple[str, ...], Job] = {}
    with sync_playwright() as playwright, playwright.chromium.launch() as browser:
        context = browser.new_context(
            java_script_enabled=False, service_workers="block"
        )
        context.route("**/*", lambda route: route.abort())
        page = context.new_page()
        for path in paths:
            if path.suffix.lower() != ".html" or path.stat().st_size > 2_000_000:
                raise ValueError("snapshots must be HTML files of at most 2 MB")
            page.set_content(
                path.read_text(encoding="utf-8"), wait_until="domcontentloaded"
            )
            cards = page.locator("article[data-job]")
            if cards.count() > 500:
                raise ValueError("at most 500 vacancies per snapshot")
            for card in cards.all():
                fields = []
                for name, limit in (
                    ("company", 160),
                    ("title", 160),
                    ("region", 100),
                    ("mode", 40),
                    ("description", 4_000),
                ):
                    element = card.locator(f"[data-field='{name}']")
                    if element.count() != 1:
                        raise ValueError(f"expected exactly one {name} field")
                    value = element.inner_text(timeout=3_000).strip()
                    if not value or len(value) > limit:
                        raise ValueError(f"empty or oversized {name} field")
                    fields.append(value)
                job = Job(*fields)
                if norm(job.mode) not in {"remote", "hybrid", "on-site", "unknown"}:
                    raise ValueError("mode must be remote, hybrid, on-site or unknown")
                jobs.setdefault(tuple(map(norm, fields[:4])), job)
    return list(jobs.values())


def evaluate(job: Job, profile: Profile) -> dict:
    corpus = norm(f"{job.title} {job.description}")
    skills = sorted({norm(skill) for skill in profile.skills})
    matched = [
        s for s in skills if re.search(rf"(?<![\w+#]){re.escape(s)}(?![\w+#])", corpus)
    ]
    exclusions = []
    if norm(job.region) != norm(profile.region):
        exclusions.append("region differs or is unspecified")
    if profile.remote_only and norm(job.mode) != "remote":
        exclusions.append("remote work not explicitly stated")
    return {
        "job": {
            "company": job.company,
            "title": job.title,
            "region": job.region,
            "mode": job.mode,
        },
        "eligible": not exclusions,
        "score": round(100 * len(matched) / len(skills)) if skills else 0,
        "matched_skills": matched,
        "missing_skills": sorted(set(skills) - set(matched)),
        "exclusions": exclusions,
    }
