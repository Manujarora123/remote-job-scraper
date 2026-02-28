# Canonical Fingerprint Contract (Issue #3)

Primary fingerprint:

`sha256(normalized_apply_url + company_norm + title_norm + location_norm)`

Normalization rules:
1. `normalized_apply_url`
   - lowercase scheme + host
   - remove URL fragment
   - collapse duplicate slashes and trim trailing slash (except root)
   - remove known tracking params (`utm_*`, `src`, `source`, `ref`, `feedId`, etc.)
   - stable sort remaining query params
2. `company_norm`, `title_norm`, `location_norm`
   - lowercase
   - trim + collapse whitespace
   - location canonicalizes `wfh`/`work from home` -> `remote`
   - location canonicalizes `india remote` and `remote india` -> `remote india`

Secondary trace fields (NOT primary dedupe keys):
- LinkedIn/source IDs (`jobId`, `source_job_id`, `source_ids`)

Usage intent:
- Search/scrape stage dedupe on primary fingerprint.
- Apply stage block if primary fingerprint has already been seen/applied.
