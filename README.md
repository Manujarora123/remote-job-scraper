# Remote Job Scraper

Automated job scraper for Customer Success and Business Development roles (India-focused, remote).

## Setup

```bash
cd job-scraper
pip install -r requirements.txt
```

## Usage

### Manual Run
```bash
python run_scraper.py
```

### Cron Setup (every 3 hours)
```bash
# Add to crontab
0 */3 * * * cd /path/to/job-scraper && python run_scraper.py >> scraper.log 2>&1
```

Or use OpenClaw cron:
```
/cron add --schedule "every 3 hours" --payload "run job scraper" --session isolated
```

## Output Files

| File | Description |
|------|-------------|
| `output/all_jobs.json` | All scraped jobs |
| `output/customer_success.json` | CS roles only |
| `output/business_development.json` | BD roles only |
| `output/last_run.json` | Run statistics |

## Job Schema (for agents)

```json
{
  "id": "abc123...",
  "title": "Customer Success Manager",
  "company": "TechCorp",
  "location": "Remote / India",
  "remote": true,
  "job_type": "customer_success",
  "source": "remote_ok",
  "source_url": "https://remoteok.com/...",
  "description": "...",
  "posted_date": "2026-02-24T...",
  "scraped_at": "2026-02-24T...",
  "salary": null,
  "apply_url": "https://remoteok.com/..."
}
```

## Sources

- Remote OK
- We Work Remotely  
- Indeed (India remote)
- LinkedIn (planned)
- Naukri (planned)

## Adding New Sources

Edit `job_scraper.py` and add a new `scrape_*` method. Follow the pattern:

```python
async def scrape_new_source(self) -> List[Job]:
    jobs = []
    # Scrape logic here
    return jobs
```

Then add to `scrape_all()` tasks list.
