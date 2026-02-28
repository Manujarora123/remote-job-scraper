import unittest

from pipeline.eligibility_scoring import (
    ELIGIBILITY_PASS,
    PassThroughEligibilityScorer,
    EligibilityResult,
    evaluate_job,
    scorer_from_config,
)


class DummyJob:
    title = "Customer Success Manager"


class TestEligibilityScoringScaffold(unittest.TestCase):
    def test_default_pass_through_result(self):
        scorer = PassThroughEligibilityScorer()

        result = scorer.evaluate(DummyJob()).to_dict()

        self.assertEqual(result["eligibility_status"], ELIGIBILITY_PASS)
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["score_breakdown"], {"baseline_pass_through": 1.0})
        self.assertEqual(result["rejection_reasons"], [])

    def test_factory_honors_default_score(self):
        scorer = scorer_from_config({"default_score": 0.75})

        result = scorer.evaluate(DummyJob()).to_dict()

        self.assertEqual(result["score"], 0.75)
        self.assertEqual(result["score_breakdown"], {"baseline_pass_through": 0.75})

    def test_to_dict_is_deterministic(self):
        raw = EligibilityResult(
            eligibility_status="pass",
            score=0.123456,
            score_breakdown={"z": 0.3333333, "a": 0.7777777},
            rejection_reasons=["missing_salary", "missing_salary", "title_mismatch"],
        )

        data = raw.to_dict()

        self.assertEqual(list(data["score_breakdown"].keys()), ["a", "z"])
        self.assertEqual(data["score_breakdown"]["a"], 0.7778)
        self.assertEqual(data["score_breakdown"]["z"], 0.3333)
        self.assertEqual(data["score"], 0.1235)
        self.assertEqual(data["rejection_reasons"], ["missing_salary", "title_mismatch"])

    def test_evaluate_job_helper_returns_required_fields(self):
        result = evaluate_job(DummyJob(), {"default_score": 0.9})

        self.assertEqual(
            sorted(result.keys()),
            ["eligibility_status", "rejection_reasons", "score", "score_breakdown"],
        )


if __name__ == "__main__":
    unittest.main()
