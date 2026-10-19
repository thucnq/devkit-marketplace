---
name: python-conventions
description: Conventions for Python components in a dk stack profile (batch pipelines, crawlers, LLM jobs) — layout, ruff, pytest, determinism, network adapters, secrets. Reference for /dk:build and /dk:review.
user-invocable: false
---

# Python conventions (dk stack `kind = "python"`)

## Layout
- `src/<package>/` (src layout, installed in `.venv` by `uv sync`), tests in `tests/`, recorded fixtures in `tests/fixtures/`, golden data for invariants in `tests/golden/`.
- One module per step of a pipeline (`crawl/<source>.py`, `dedupe.py`, `moderate.py`, …) and one `cli.py` (`python -m <package> <command>`) that wires them. Steps take data in and return data out; only `cli.py` touches files, environment variables and the network clients.

## Determinism (re-runs and tests must give the same result)
- Logic is pure: no `datetime.now()`, `random`, network or environment reads inside it — pass a clock, a seeded `random.Random(seed)` and clients as arguments.
- Stable ordering everywhere output is written (sort keys, `json.dumps(..., sort_keys=True, ensure_ascii=False)`), so a re-run produces a byte-identical artifact (idempotency ACs check this).
- Batch jobs write to a temp location and publish with one atomic step at the end; a failure before that leaves the previous output untouched.

## Network and LLM
- Every external source/API is an adapter class behind a small Protocol; tests use a fake or recorded fixture, never the network.
- Timeouts on every request (`httpx.Client(timeout=…)`), retries with exponential backoff + jitter, respect `Retry-After`, a User-Agent that names the project.
- LLM calls: structured output (JSON schema) validated with code before use; batch several items per call; on quota exhaustion stop cleanly and leave the rest for the next run; never send user data.
- Respect robots.txt and terms of each source; record the decision per source in an ADR.

## Style and gates
- `ruff format` + `ruff check` (rules in `pyproject.toml`, which agents must not loosen). Type hints on public functions.
- No `# noqa`, `# type: ignore`, `pytest.mark.skip/xfail`, `pragma: no cover` — the guard hook blocks them; fix the cause or ask the human.
- Secrets only from environment variables injected by GitHub Actions secrets; never log them, never write them to artifacts.
- Coverage ≥ 80% (`--cov-fail-under` in the profile); test names carry the AC id (`test_ac_<ma>_<nn>_…`).
