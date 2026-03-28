# Remote Job Scraper

Automated job scraper for Customer Success and Business Development roles.

## Sources

| Source | Status | Jobs |
|--------|--------|------|
| Remote OK | ✅ API | 174 |
| Remotive | ✅ API | 3 |
| Google Alerts (Gmail) | ✅ API | 2 |
| We Work Remotely | ⚠️ Needs fix | 0 |
| Indeed | ⚠️ Rate limited | 0 |
| Naukri | ❌ Blocked | - |
| LinkedIn | ❌ No auth | - |

**Total: ~178 jobs** (121 Customer Success, 55 Business Development)

## Setup

```bash
cd job-scraper
pip install -r requirements.txt
```

## Usage

### Run Scraper
```bash
python run_scraper.py
```

### Cron Job (every 3 hours)
```bash
# Manual cron
0 */3 * * * cd /path/to/job-scraper && python run_scraper.py
```

Or use OpenClaw cron (already configured):
```
/cron add --schedule "every 3 hours" --session isolated
```

## Output

Jobs saved to `output/`:
- `all_jobs.json` - All scraped jobs
- `customer_success.json` - CS roles only
- `business_development.json` - BD roles only
- `last_run.json` - Run statistics

### Contact Enrichment Waterfall (Issue #22)

Each job now supports deterministic founder/business email enrichment:

1. Hunter lookup
2. Apollo lookup
3. Pattern guess fallback (`first@domain`, then variants, then `info@domain`)

It records provenance per attempt (`contact_provenance`) and a confidence score (`contact_confidence`) by source:

- Hunter: `0.95`
- Apollo: `0.88`
- Pattern guess: `0.55`

Retry/backoff is built-in for transient and rate-limit failures.

Set API keys to enable provider calls:

```bash
export HUNTER_API_KEY=...
export APOLLO_API_KEY=...
```

## Job Schema

```json
{
  "id": "abc123...",
  "title": "Customer Success Manager",
  "company": "TechCorp",
  "location": "Remote",
  "remote": true,
  "job_type": "customer_success",
  "source": "remote_ok",
  "source_url": "https://remoteok.com/...",
  "apply_url": "https://remoteok.com/...",
  "founder_email": "jane@techcorp.com",
  "business_email": "jane@techcorp.com",
  "contact_email": "jane@techcorp.com",
  "contact_email_source": "hunter",
  "contact_confidence": 0.95,
  "contact_provenance": [{"source": "hunter", "attempt": 1, "status": "success"}]
}
```

## Google Alerts Integration

Uses Gmail API to read Google Alert emails:
- Searches "customer success", for: "business development", "account manager"
- Also reads LinkedIn job notification emails
- Extracts job URLs from email body

Requires Gmail API server running on `localhost:3001`.

## LinkedIn Authentication Bootstrap

The resolver uses LinkedIn session cookies (`li_at` + `JSESSIONID`) for the
Voyager API tier.  A helper script captures them via a headed browser login.

### 1. Capture credentials (one-time)

```bash
# Print cookies to stdout only
python scripts/capture_linkedin_auth.py

# Save cookies to .env.local AND storage-state JSON
python scripts/capture_linkedin_auth.py --save-env --save-storage-state
```

A headed Chromium window opens → log in to LinkedIn → return to terminal and
press ENTER.  The script writes:

| Flag | Output |
|------|--------|
| *(none)* | Prints `LI_AT` / `JSESSIONID` to stdout |
| `--save-env` | Upserts values into `.env.local` |
| `--save-storage-state [PATH]` | Saves Playwright storage-state JSON (default `linkedin_storage_state.json`) |

### 2. Use with the resolver

```bash
# Auto-loaded from .env.local (no flags needed)
python resolve_apply_paths.py --input output/all_jobs.json

# Or pass explicitly
python resolve_apply_paths.py \
  --linkedin-li-at "$LI_AT" \
  --linkedin-jsessionid "$JSESSIONID"

# Or use Playwright storage state
python resolve_apply_paths.py --storage-state linkedin_storage_state.json
```

### ⚠️ Security notes

* **Never commit** `.env.local`, `.env`, or `*_storage_state.json` — they
  contain session secrets.  These are already in `.gitignore`.
* Cookies expire when LinkedIn invalidates the session (typically 1-3 months).
  Re-run the capture script when requests start returning `401`/`403`.

## Next Steps

1. **Fix We Work Remotely** - Site changed selectors
2. **Add more sources** - Check for more job board APIs
3. **Improve Google Alerts parsing** - Extract actual job titles/companies
4. **Add application automation** - Integrate with job-application-tool

## History

- Created: 2026-02-24
- Initial sources: Remote OK API, Remotive API
- Added Google Alerts via Gmail API
- Naukri blocked (requires real browser + CAPTCHA)
- Indeed rate limited

## Verification + Compliance (Issue #23)
- Module: pipeline/verification_compliance.py
- Prechecks: syntax + MX + catch-all
- Provider adapters: NeverBounce / ZeroBounce
- Suppression + opt-out checks
- Guardrails: max touches + send windows
- Audit logging: append-only JSONL
See VERIFICATION_COMPLIANCE.md for usage.
