import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("gh_pr_watch.py")
MODULE_SPEC = importlib.util.spec_from_file_location("gh_pr_watch", MODULE_PATH)
watcher = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(watcher)


def check_run(name, conclusion, started, workflow="Hermes", status="COMPLETED"):
    return {
        "__typename": "CheckRun",
        "name": name,
        "workflowName": workflow,
        "status": status,
        "conclusion": conclusion,
        "startedAt": started,
        "detailsUrl": "https://example.com/check",
    }


def status_context(name, state="SUCCESS"):
    return {
        "__typename": "StatusContext",
        "context": name,
        "state": state,
        "startedAt": "2026-09-01T12:00:00Z",
        "targetUrl": "",
    }


def sample_pr(**overrides):
    value = {
        "closed": False,
        "head_sha": "abc123",
        "is_draft": False,
    }
    value.update(overrides)
    return value


def sample_checks(**overrides):
    value = {
        "all_passing": True,
        "pending_count": 0,
        "failed_count": 0,
        "passed_count": 3,
        "ignored_count": 2,
        "pending": [],
        "failed": [],
        "ignored": [],
        "fin_review": {
            "name": watcher.FIN_REVIEW_CHECK,
            "result": "pass",
            "conclusion": "SUCCESS",
        },
    }
    value.update(overrides)
    return value


class CheckTests(unittest.TestCase):
    def test_normalizes_hermes_review_check(self):
        result = watcher.normalize_check(
            check_run("pr-pipeline / code-review", "SUCCESS", "2026-09-01T12:00:00Z")
        )
        self.assertEqual(result["name"], watcher.FIN_REVIEW_CHECK)
        self.assertEqual(result["result"], "pass")

    def test_ignores_approval_gate_and_bors(self):
        summary = watcher.summarize_checks(
            [
                status_context("hermes/approval-gate", "PENDING"),
                status_context("bors", "PENDING"),
                status_context("ci/tests", "SUCCESS"),
            ]
        )
        self.assertTrue(summary["all_passing"])
        self.assertEqual(summary["ignored_count"], 2)
        self.assertEqual(summary["passed_count"], 1)

    def test_skipped_duplicate_does_not_hide_substantive_failure(self):
        summary = watcher.summarize_checks(
            [
                check_run("pr-pipeline / code-review", "FAILURE", "2026-09-01T12:00:00Z"),
                check_run("pr-pipeline / code-review", "SKIPPED", "2026-09-01T12:05:00Z"),
            ]
        )
        self.assertEqual(summary["fin_review"]["result"], "fail")

    def test_newer_substantive_check_wins(self):
        summary = watcher.summarize_checks(
            [
                check_run("pr-pipeline / code-review", "FAILURE", "2026-09-01T12:00:00Z"),
                check_run("pr-pipeline / code-review", "SUCCESS", "2026-09-01T12:05:00Z"),
            ]
        )
        self.assertEqual(summary["fin_review"]["result"], "pass")


class ReviewTests(unittest.TestCase):
    def test_lgtm_must_match_head_sha(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "new-sha",
            "reviews": [
                {
                    "id": "review-1",
                    "author": {"login": "fin-review"},
                    "body": "LGTM",
                    "submittedAt": "2026-09-01T12:00:00Z",
                    "commit": {"oid": "old-sha"},
                }
            ],
        }
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {})
        self.assertFalse(result["lgtm_for_head"])

    def test_fin_review_bot_comment_is_surfaced(self):
        pr = {"number": 1, "repo": "fintoc-com/example", "head_sha": "abc", "reviews": []}
        comments = [
            {
                "id": 10,
                "user": {"login": "fin-review[bot]"},
                "body": "Please handle this.",
                "created_at": "2026-09-01T12:00:00Z",
            },
            {
                "id": 11,
                "user": {"login": "other-bot[bot]"},
                "body": "Noise",
            },
        ]
        with patch.object(watcher, "gh_api_list_paginated", return_value=comments):
            result = watcher.fetch_fin_review(pr, {})
        self.assertEqual([item["id"] for item in result["new_items"]], ["10"])


class ActionTests(unittest.TestCase):
    def test_ready_only_when_checks_pass_and_head_has_lgtm(self):
        actions = watcher.recommend_actions(
            sample_pr(), sample_checks(), {"lgtm_for_head": True, "new_items": []}
        )
        self.assertEqual(actions, ["ready_for_review"])

    def test_draft_without_review_requests_fin_review(self):
        checks = sample_checks(fin_review=None)
        actions = watcher.recommend_actions(
            sample_pr(is_draft=True), checks, {"lgtm_for_head": False, "new_items": []}
        )
        self.assertEqual(actions, ["request_fin_review"])

    def test_skipped_review_check_is_not_ready(self):
        checks = sample_checks(
            fin_review={
                "name": watcher.FIN_REVIEW_CHECK,
                "result": "pass",
                "conclusion": "SKIPPED",
            }
        )
        actions = watcher.recommend_actions(
            sample_pr(), checks, {"lgtm_for_head": True, "new_items": []}
        )
        self.assertEqual(actions, ["request_fin_review"])

    def test_review_findings_precede_generic_ci_failure(self):
        failed = [
            {"name": watcher.FIN_REVIEW_CHECK, "result": "fail"},
            {"name": "ci/tests", "result": "fail"},
        ]
        checks = sample_checks(
            all_passing=False,
            failed_count=2,
            failed=failed,
            fin_review=failed[0],
        )
        review = {
            "lgtm_for_head": False,
            "new_items": [{"kind": "review_comment", "id": "10"}],
        }
        actions = watcher.recommend_actions(sample_pr(), checks, review)
        self.assertEqual(actions, ["process_fin_review_findings", "diagnose_ci_failure"])


if __name__ == "__main__":
    unittest.main()
