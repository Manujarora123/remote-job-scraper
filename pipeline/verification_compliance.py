"""Verification + compliance module (Issue #23).

Features:
- Email prechecks: syntax, MX availability, catch-all probe hook
- Provider abstraction for NeverBounce / ZeroBounce style responses
- Suppression + opt-out handling
- Guardrails: max touches, send windows, append-only audit log
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
import json
import re
from pathlib import Path
from typing import Callable, Protocol


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


@dataclass(frozen=True)
class PrecheckResult:
    email: str
    syntax_valid: bool
    has_mx: bool
    catch_all: bool | None

    @property
    def ok(self) -> bool:
        return self.syntax_valid and self.has_mx and self.catch_all is not True


@dataclass(frozen=True)
class ProviderVerificationResult:
    provider: str
    status: str
    raw: dict = field(default_factory=dict)

    @property
    def deliverable(self) -> bool:
        return self.status in {"valid", "catchall"}


class VerificationProvider(Protocol):
    name: str

    def verify(self, email: str) -> ProviderVerificationResult:
        ...


class NeverBounceProvider:
    """Adapter over a NeverBounce client-like object with .verify(email)."""

    name = "neverbounce"

    def __init__(self, client: object) -> None:
        self._client = client

    def verify(self, email: str) -> ProviderVerificationResult:
        payload = self._client.verify(email)
        status = str(payload.get("result", "unknown")).lower()
        mapped = {
            "valid": "valid",
            "invalid": "invalid",
            "disposable": "invalid",
            "catchall": "catchall",
            "unknown": "unknown",
        }.get(status, "unknown")
        return ProviderVerificationResult(provider=self.name, status=mapped, raw=payload)


class ZeroBounceProvider:
    """Adapter over a ZeroBounce client-like object with .validate(email)."""

    name = "zerobounce"

    def __init__(self, client: object) -> None:
        self._client = client

    def verify(self, email: str) -> ProviderVerificationResult:
        payload = self._client.validate(email)
        status = str(payload.get("status", "unknown")).lower()
        mapped = {
            "valid": "valid",
            "invalid": "invalid",
            "do_not_mail": "invalid",
            "spamtrap": "invalid",
            "catch-all": "catchall",
            "catchall": "catchall",
            "unknown": "unknown",
        }.get(status, "unknown")
        return ProviderVerificationResult(provider=self.name, status=mapped, raw=payload)


class SuppressionList:
    def __init__(self, initial: set[str] | None = None) -> None:
        self._emails = {e.lower().strip() for e in (initial or set())}

    def add(self, email: str) -> None:
        self._emails.add(email.lower().strip())

    def contains(self, email: str) -> bool:
        return email.lower().strip() in self._emails

    def to_list(self) -> list[str]:
        return sorted(self._emails)


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event_type: str, data: dict) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class ComplianceGuardrails:
    def __init__(
        self,
        *,
        max_touches_per_contact: int,
        send_window_start: str = "09:00",
        send_window_end: str = "18:00",
        suppression_list: SuppressionList | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.max_touches_per_contact = max_touches_per_contact
        self.send_window_start = _parse_hhmm(send_window_start)
        self.send_window_end = _parse_hhmm(send_window_end)
        self.suppression_list = suppression_list or SuppressionList()
        self.audit_logger = audit_logger

    def within_send_window(self, dt: datetime) -> bool:
        current = dt.time()
        return self.send_window_start <= current <= self.send_window_end

    def can_send(
        self,
        *,
        email: str,
        touches_so_far: int,
        opted_out: bool,
        now: datetime,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if opted_out:
            reasons.append("opted_out")
        if self.suppression_list.contains(email):
            reasons.append("suppressed")
        if touches_so_far >= self.max_touches_per_contact:
            reasons.append("max_touches_exceeded")
        if not self.within_send_window(now):
            reasons.append("outside_send_window")

        allowed = not reasons
        if self.audit_logger:
            self.audit_logger.log(
                "compliance_check",
                {
                    "email": email,
                    "allowed": allowed,
                    "reasons": reasons,
                    "touches_so_far": touches_so_far,
                },
            )
        return allowed, reasons


class EmailVerifier:
    def __init__(
        self,
        *,
        provider: VerificationProvider,
        mx_checker: Callable[[str], bool],
        catch_all_checker: Callable[[str], bool | None] | None = None,
    ) -> None:
        self.provider = provider
        self.mx_checker = mx_checker
        self.catch_all_checker = catch_all_checker or (lambda _domain: None)

    def precheck(self, email: str) -> PrecheckResult:
        email_norm = email.lower().strip()
        syntax_valid = bool(EMAIL_RE.match(email_norm))
        domain = email_norm.split("@", 1)[1] if syntax_valid else ""
        has_mx = syntax_valid and self.mx_checker(domain)
        catch_all = self.catch_all_checker(domain) if has_mx else None
        return PrecheckResult(
            email=email_norm,
            syntax_valid=syntax_valid,
            has_mx=bool(has_mx),
            catch_all=catch_all,
        )

    def verify(self, email: str) -> tuple[PrecheckResult, ProviderVerificationResult | None]:
        pre = self.precheck(email)
        if not pre.ok:
            return pre, None
        return pre, self.provider.verify(pre.email)


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":", 1)
    return time(hour=int(hh), minute=int(mm))
