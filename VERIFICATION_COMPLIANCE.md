# Verification + Compliance Module (Issue #23)

`pipeline/verification_compliance.py` adds pre-send guardrails for outbound outreach.

## Capabilities

1. **Email prechecks**
   - Syntax validation
   - MX presence check (via injectable `mx_checker`)
   - Catch-all precheck (via injectable `catch_all_checker`)

2. **Provider abstraction**
   - `VerificationProvider` protocol
   - `NeverBounceProvider` adapter
   - `ZeroBounceProvider` adapter
   - Normalized statuses: `valid | invalid | catchall | unknown`

3. **Suppression + opt-out handling**
   - `SuppressionList` supports fast lookups
   - `ComplianceGuardrails.can_send(...)` denies if `opted_out` or suppressed

4. **Guardrails + audit log**
   - Max touches per contact
   - Send window checks (`HH:MM` local time)
   - Append-only JSONL audit logging via `AuditLogger`

## Example

```python
from datetime import datetime
from pipeline.verification_compliance import (
    EmailVerifier,
    NeverBounceProvider,
    ComplianceGuardrails,
    SuppressionList,
)

provider = NeverBounceProvider(client=nb_client)
verifier = EmailVerifier(
    provider=provider,
    mx_checker=my_mx_lookup,
    catch_all_checker=my_catch_all_probe,
)

precheck, provider_result = verifier.verify("person@example.com")

suppression = SuppressionList({"blocked@example.com"})
guards = ComplianceGuardrails(
    max_touches_per_contact=3,
    send_window_start="09:00",
    send_window_end="18:00",
    suppression_list=suppression,
)

allowed, reasons = guards.can_send(
    email="person@example.com",
    touches_so_far=1,
    opted_out=False,
    now=datetime.now(),
)
```

## Notes
- MX and catch-all checks are intentionally injected as callables so DNS/network implementations can be swapped per environment.
- Provider adapters are thin wrappers, making API clients easy to mock in tests.
