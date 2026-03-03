# LinkedIn Jobs-Guest JD Parsing Notes

## Endpoint
`https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{JOB_ID}`

No auth/API key/cookies required.

## Required headers
- `User-Agent` (browser-like)
- `Accept: text/html,application/xhtml+xml`
- `Accept-Language: en-US,en;q=0.9`

## Rate limits and safety
- Keep >=2s between requests
- Stay around <=10 requests / 5 min
- On `429`, back off 2-5 minutes before retry

## Selectors (verified early 2026)
- Title: `h2.top-card-layout__title`
- Company: `a.topcard__org-name-link`
- Location: `span.topcard__flavor--bullet`
- Description: `div.show-more-less-html__markup` (fallbacks supported)
- Criteria: `li.description__job-criteria-item`

## Validation
Treat parse as valid only when combined extracted text is >300 chars.

## Fallback strategy
If guest API is short/empty/blocked:
- fallback to Playwright extraction from the LinkedIn job page.

## Local scripts
- `linkedin_jd_scraper.py` (standalone URL/ID parser + scraper)
- `resolve_apply_paths.py` (adds `application_mode`, `application_url`, `ats_vendor` routing metadata)
- Google Alerts enrichment uses guest API first, then Playwright fallback.
