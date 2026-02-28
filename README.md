# Remote Job Scraper

Scrapes Customer Success & Business Development remote jobs (India) from 5 sources every 2-5 hours. Outputs JSON for agent-based auto-application pipeline.

## Sources
| Source | Method | Auth |
|--------|--------|------|
| LinkedIn | HTTP + cookies | Session cookie |
| Indeed | HTTP scraping | None |
| Remote OK | Public JSON API | None |
| We Work Remotely | HTTP scraping | None |
| Naukri | HTTP scraping | None |

## Quick Start
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # add LinkedIn cookie if needed
python run.py          # one-shot scrape
```

## Cron (every 3 hours)
```cron
0 */3 * * * cd /path/to/remote-job-scraper && python run.py >> logs/cron.log 2>&1
```

## Eligibility + Scoring Config (Issue #2 scaffold)
Configured in `config.py` under `ELIGIBILITY_SCORING` and via `.env`:

- `ELIGIBILITY_SCORING_ENABLED` (default `true`)
- `ELIGIBILITY_POLICY` (default `pass_through`)
- `ELIGIBILITY_DEFAULT_SCORE` (default `1.0`)

`hard_filters`, `weights`, and `thresholds` are present as forward-compatible schema only.
They are **not enforced** in this scaffold release.

## Output
Results go to `output/jobs_YYYYMMDD_HHMMSS.json` and `output/latest.json` (symlink).

Each job now includes deterministic Issue #2 scaffold fields:
- `eligibility_status` (`pass|review|reject`)
- `score` (float)
- `score_breakdown` (object)
- `rejection_reasons` (string array)

Issue #3 adds canonical dedupe fields:
- `normalized_apply_url`, `company_norm`, `title_norm`, `location_norm`
- `primary_fingerprint` (sha256 canonical key)
- `source_job_id`, `source_ids` (secondary trace identifiers)

Current default policy is permissive pass-through (no thresholds enforced yet).

## Architecture
```
run.py                  ← entry point (cron-friendly)
config.py               ← search terms, filters, source toggles
scraper.py              ← orchestrator: runs adapters, dedupes, outputs JSON
models.py               ← Job dataclass + JSON schema
pipeline/
  eligibility_scoring.py ← Issue #2 pluggable eligibility/scoring scaffold
adapters/
  base.py               ← BaseAdapter ABC
  linkedin.py           ← LinkedIn Jobs scraper
  indeed.py             ← Indeed scraper
  remoteok.py           ← Remote OK JSON API
  weworkremotely.py      ← WWR scraper
  naukri.py             ← Naukri scraper
output/                 ← JSON results
logs/                   ← cron logs
```
