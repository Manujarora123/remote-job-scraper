"""Eligibility + scoring scaffold for pipeline integration.

Issue #2 scope:
- Pluggable interfaces (policy can be swapped later)
- Permissive defaults (pass-through behavior)
- Deterministic output schema for downstream consumers

This module intentionally does NOT enforce hard rejection thresholds yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


ELIGIBILITY_PASS = "pass"
ELIGIBILITY_REVIEW = "review"
ELIGIBILITY_REJECT = "reject"


@dataclass(frozen=True)
class EligibilityResult:
    """Deterministic policy output attached to each job."""

    eligibility_status: str = ELIGIBILITY_PASS
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    rejection_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Stable JSON shape with deterministic key ordering and numeric precision."""
        ordered_breakdown = {
            key: float(round(self.score_breakdown[key], 4))
            for key in sorted(self.score_breakdown.keys())
        }
        ordered_reasons = sorted(set(self.rejection_reasons))
        return {
            "eligibility_status": self.eligibility_status,
            "score": float(round(self.score, 4)),
            "score_breakdown": ordered_breakdown,
            "rejection_reasons": ordered_reasons,
        }


class EligibilityScorer(Protocol):
    """Interface for pluggable eligibility/scoring policies."""

    def evaluate(self, job: object) -> EligibilityResult:
        """Evaluate a job and return deterministic structured output."""
        ...


class PassThroughEligibilityScorer:
    """Default permissive scorer.

    - Always marks job as pass
    - Emits deterministic schema with configurable baseline score
    - Keeps rejection_reasons empty until future hard-filter policy is enabled
    """

    def __init__(
        self,
        *,
        baseline_score: float = 1.0,
        breakdown_label: str = "baseline_pass_through",
    ) -> None:
        self.baseline_score = float(baseline_score)
        self.breakdown_label = breakdown_label

    def evaluate(self, job: object) -> EligibilityResult:
        return EligibilityResult(
            eligibility_status=ELIGIBILITY_PASS,
            score=self.baseline_score,
            score_breakdown={self.breakdown_label: self.baseline_score},
            rejection_reasons=[],
        )


def scorer_from_config(policy_config: dict | None) -> EligibilityScorer:
    """Factory for scorer selection.

    Current behavior always returns permissive pass-through scorer.
    The config schema exists now so stricter policy can be introduced later
    without breaking call-sites.
    """
    cfg = policy_config or {}
    baseline_score = cfg.get("default_score", 1.0)
    return PassThroughEligibilityScorer(baseline_score=baseline_score)


def evaluate_job(job: object, policy_config: dict | None) -> dict:
    """Convenience helper used by pipeline orchestration layers."""
    scorer = scorer_from_config(policy_config)
    return scorer.evaluate(job).to_dict()
