# Interface Contract: `remote-job-scraper` → `job-application-tool`

Owner: Integration / issues #1-#5

## 1) Boundary and ownership

- Repos remain separate.
- `remote-job-scraper` owns discovery (search + eligibility scaffold output).
- `job-application-tool` owns application execution lifecycle + state machine.
- Orchestrator is the only bridge.

## 2) Handoff file contract

Primary handoff artifact: JSON file from scraper.

Default path used by orchestrator:
- `<remote-job-scraper>/output/latest.json`

Fallback for dry-run/testing:
- `<remote-job-scraper>/output/sample_scored_job.json`

### Required envelope

```json
{
  "run_id": "20260228_194500",
  "scraped_at": "2026-02-28T19:45:00",
  "jobs": [ /* job objects */ ]
}
```

### Job object fields consumed by orchestrator

- `apply_url` (preferred) OR `url` (fallback) — required for executable candidate
- `title` (optional but recommended)
- `company` (optional but recommended)
- `location` (optional)
- `job_id` (optional source ID)
- `eligibility_status` (`pass|review|reject`; default behavior processes only `pass`)
- Remaining fields are stored in `source_payload_json` for traceability.

## 3) Candidate enqueue contract into state machine

Orchestrator writes into `job-application-tool` via repository API:

- `upsert_candidate(CandidateInput)` with
  - `source_repo="remote-job-scraper"`
  - `source_job_id=job.job_id`
  - `source_payload=full job object`

Fingerprint/idempotency contract (already implemented in `job-application-tool`):

```text
sha256(normalized_apply_url + company_norm + title_norm + location_norm)
```

## 4) State transition contract

Per candidate, orchestrator target flow is:

`DISCOVERED -> QUEUED -> APPLYING -> APPLIED`

On execution failure:

`APPLYING -> SUBMISSION_FAILED`

Candidates already in `APPLIED` are skipped idempotently.

## 5) Command-level contract

Orchestrator optional scrape command (in scraper repo):

```bash
python run.py
```

(If a different issue branch changes the entrypoint, pass `--scraper-command`.)

Application execution command (in application repo):

```bash
python job_applicant.py <apply_url>
```

Dry-run propagation:

```bash
python job_applicant.py <apply_url> --dry-run
```

## 6) Alerts contract

Orchestrator sends run summary to Telegram DM using bot API envs:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

If envs are absent, pipeline still runs and only writes local summary JSON.

## 7) Output from orchestrator

Run summary JSON:

- `<job-application-tool>/out/orchestrator_summary_latest.json`

Contains:
- scrape step status
- aggregate counters (`applied`, `submission_failed`, `skipped`, etc.)
- per-job outcomes and errors
