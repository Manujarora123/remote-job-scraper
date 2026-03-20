from datetime import datetime
import json

from pipeline.verification_compliance import (
    AuditLogger,
    ComplianceGuardrails,
    EmailVerifier,
    NeverBounceProvider,
    SuppressionList,
    ZeroBounceProvider,
)


class _NBClient:
    def verify(self, email: str) -> dict:
        return {"address": email, "result": "valid"}


class _ZBClient:
    def validate(self, email: str) -> dict:
        return {"address": email, "status": "catch-all"}


def test_precheck_blocks_invalid_syntax_and_mx():
    verifier = EmailVerifier(
        provider=NeverBounceProvider(_NBClient()),
        mx_checker=lambda domain: domain == "example.com",
        catch_all_checker=lambda _domain: False,
    )

    pre, provider_result = verifier.verify("bad-email")
    assert pre.syntax_valid is False
    assert pre.has_mx is False
    assert provider_result is None


def test_precheck_blocks_catch_all_before_provider_call():
    verifier = EmailVerifier(
        provider=NeverBounceProvider(_NBClient()),
        mx_checker=lambda _domain: True,
        catch_all_checker=lambda _domain: True,
    )

    pre, provider_result = verifier.verify("person@example.com")
    assert pre.catch_all is True
    assert provider_result is None


def test_provider_mapping_neverbounce_and_zerobounce():
    nb = NeverBounceProvider(_NBClient()).verify("a@example.com")
    zb = ZeroBounceProvider(_ZBClient()).verify("a@example.com")

    assert nb.status == "valid"
    assert nb.deliverable is True

    assert zb.status == "catchall"
    assert zb.deliverable is True


def test_suppression_and_opt_out_and_touch_guardrail(tmp_path):
    suppression = SuppressionList({"blocked@example.com"})
    logger = AuditLogger(tmp_path / "audit.log")
    guardrails = ComplianceGuardrails(
        max_touches_per_contact=3,
        send_window_start="09:00",
        send_window_end="18:00",
        suppression_list=suppression,
        audit_logger=logger,
    )

    allowed, reasons = guardrails.can_send(
        email="blocked@example.com",
        touches_so_far=3,
        opted_out=True,
        now=datetime(2026, 3, 20, 11, 0, 0),
    )

    assert allowed is False
    assert sorted(reasons) == ["max_touches_exceeded", "opted_out", "suppressed"]

    lines = (tmp_path / "audit.log").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["event_type"] == "compliance_check"
    assert payload["data"]["allowed"] is False


def test_send_window_enforced():
    guardrails = ComplianceGuardrails(max_touches_per_contact=2)

    allowed, reasons = guardrails.can_send(
        email="ok@example.com",
        touches_so_far=0,
        opted_out=False,
        now=datetime(2026, 3, 20, 22, 15, 0),
    )

    assert allowed is False
    assert reasons == ["outside_send_window"]
