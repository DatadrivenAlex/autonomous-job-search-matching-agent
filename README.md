# Autonomous Job-Search & Matching Agent

An explainable, local-first reference implementation for collecting vacancy cards from user-supplied HTML snapshots, ranking them against an explicit profile, deduplicating them, and saving each run for later review. It draws on the author's actual automation pipeline work in Python, Playwright and SQLite, including deduplication, human-approved application gates and a job-tracking pipeline; it is a clean-room, synthetic-data portfolio example, not the original pipeline or a live job-finding service.

## What it does

- Uses Playwright to parse bounded local HTML snapshots; page JavaScript is disabled and every network request is aborted.
- Deduplicates postings by normalized company, title, region and work mode across all input snapshots.
- Scores transparent skill overlap, with explicit region/remote exclusions and matched/missing terms.
- Saves every run transactionally to SQLite, or optional PostgreSQL through `JOBMATCH_POSTGRES_DSN`.
- Optionally adds a short LLM explanation for eligible matches. This is off by default; only score and skill labels are sent, never the listing, URL, profile, resume or name. The endpoint is pinned to the public API, request storage is disabled, and no application is ever submitted.
- Makes no external network requests when run without the opt-in LLM flag. Apply, message or account automation is deliberately not included.

## Run the synthetic example

```bash
uv sync --all-extras
uv run playwright install chromium
uv run ruff check .
uv run pytest -q
uv run python -m jobmatch examples/jobs.html --profile examples/profile.json
```

Outputs include a unique run ID and a ranked JSON explanation. Example companies and postings are fictitious. Snapshot sources must provide `article[data-job]` cards with exactly one `[data-field]` for company, title, region, mode and description. Work mode must be `remote`, `hybrid`, `on-site` or `unknown`; uncertainty is excluded for remote-only profiles. Input limits: 50 snapshots, 2 MB each, 500 jobs per file, and bounded field lengths.

Profile JSON accepts only `skills`, `region`, and boolean `remote_only`; avoid putting contact details or resumes in it. The exact overlap score is a transparent keyword baseline, not a calibrated hiring prediction. Review listings and decide next steps yourself.

## Optional LLM note

Install the optional LLM dependency, then explicitly set `OPENAI_API_KEY` and `JOBMATCH_LLM_MODEL` and add `--llm-explain`. This sends only skill labels and score for at most three eligible matches to the pinned OpenAI API endpoint; credentials stay in the environment. Review provider terms and your data choices before enabling it. The base workflow remains local and works without an API key.

For PostgreSQL, install `.[postgres]` and set `JOBMATCH_POSTGRES_DSN` to a local database DSN. The optional Docker image runs the synthetic example:

```bash
docker build -t jobmatch .
docker run --rm jobmatch
```

## Security boundaries

- No scraped live pages, remote URL fetching, login, cookies, proxying, CAPTCHA handling, mass collection, application submission, outbound messages, or automatic profile changes.
- Browser JavaScript is disabled; network requests are blocked. Feed only snapshots you have permission to use.
- Store files and the default SQLite database locally; protect the machine and remove any data you no longer need.
- LLM use is an explicit opt-in and never controls a decision or action. No candidate is contacted automatically.

## Roadmap

For a real deployment, add source-specific permitted ingestion, provenance and retention policies, stronger explainable matching, monitored queue state, review-first application workflows, rate limits and access controls. None of that is represented as implemented here.

## License

MIT; see [LICENSE](LICENSE).
