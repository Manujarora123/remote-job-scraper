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
