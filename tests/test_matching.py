import json
import sqlite3
from pathlib import Path

import pytest

from jobmatch.__main__ import read_profile, store
from jobmatch.core import Job, Profile, collect, evaluate, norm


def test_collect_playwright_snapshot_and_rank():
    root = Path(__file__).parents[1]
    jobs = collect([root / "examples/jobs.html"])
    assert len(jobs) == 3
    profile = read_profile(root / "examples/profile.json")
    first = evaluate(jobs[0], profile)
    assert first["eligible"] and first["score"] == 100
    onsite = next(job for job in jobs if job.mode == "on-site")
    assert (
        "remote work not explicitly stated" in evaluate(onsite, profile)["exclusions"]
    )


def test_duplicate_cards_and_normalized_key(tmp_path):
    html = """<article data-job><b data-field='company'>Acme</b><i data-field='title'>Python</i>
    <i data-field='region'>Germany</i><i data-field='mode'>remote</i>
    <p data-field='description'>FastAPI work.</p></article>"""
    file = tmp_path / "jobs.html"
    file.write_text(html + html.replace("Acme", "  ACME  "), encoding="utf-8")
    assert len(collect([file])) == 1
    assert norm("  ÄBC   Test ") == "äbc test"


def test_duplicate_across_snapshots(tmp_path):
    root = Path(__file__).parents[1]
    assert len(collect([root / "examples/jobs.html"] * 2)) == 3


def test_region_mismatch_excludes_job():
    job = Job("Acme", "Python API", "France", "remote", "Python API")
    result = evaluate(job, Profile(("Python",), "Germany", True))
    assert not result["eligible"]
    assert result["exclusions"] == ["region differs or is unspecified"]


def test_unknown_work_mode_fails_closed():
    job = Job("Acme", "Python API", "Germany", "unknown", "Python API")
    result = evaluate(job, Profile(("Python",), "Germany", True))
    assert not result["eligible"]


def test_skills_are_not_matched_inside_larger_words():
    job = Job("Acme", "Pythonista", "Germany", "remote", "FastAPI")
    assert evaluate(job, Profile(("Python",), "Germany", False))["score"] == 0


def test_profile_rejects_extra_fields(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "skills": ["Python"],
                "region": "Germany",
                "remote_only": True,
                "email": "private@example.test",
            }
        )
    )
    with pytest.raises(ValueError):
        read_profile(profile)


def test_snapshot_rejects_remote_and_oversize(tmp_path):
    remote = tmp_path / "x.html"
    remote.write_text(
        '<article data-job><iframe src="https://example.com"></iframe></article>'
    )
    with pytest.raises(ValueError):
        collect([remote])
    too_big = tmp_path / "big.html"
    too_big.write_bytes(b" " * 2_000_001)
    with pytest.raises(ValueError):
        collect([too_big])


def test_storage_creates_independent_auditable_runs(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBMATCH_POSTGRES_DSN", raising=False)
    database = tmp_path / "runs.sqlite3"
    rows = [{"score": 75, "matched_skills": ["python"]}]
    first, second = store(rows, str(database)), store(rows, str(database))
    with sqlite3.connect(database) as connection:
        records = connection.execute(
            "SELECT run_id, results_json FROM match_runs"
        ).fetchall()
    assert first != second and len(records) == 2
    assert json.loads(records[0][1]) == rows


def test_llm_note_input_is_allowlisted(monkeypatch):
    from jobmatch.__main__ import explain

    captured = {}

    class Responses:
        def create(self, **kwargs):
            captured.update(kwargs)

            class Result:
                output_text = "Matches three required skills."

            return Result()

    class Client:
        responses = Responses()

    monkeypatch.setenv("JOBMATCH_LLM_MODEL", "test")
    row = {
        "score": 100,
        "matched_skills": ["Python"],
        "missing_skills": [],
        "job": {"company": "private name", "title": "secret title"},
        "url": "https://private.test",
        "description": "private text",
    }
    assert explain(row, Client()) == "Matches three required skills."
    sent = json.loads(captured["input"])
    assert set(sent) == {"score", "matched_skills", "missing_skills"}
    assert captured["store"] is False
    assert "secret" not in captured["instructions"]
