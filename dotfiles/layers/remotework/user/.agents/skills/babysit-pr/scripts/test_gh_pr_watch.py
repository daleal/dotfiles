import importlib.util
import io
import json
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("gh_pr_watch.py")
MODULE_SPEC = importlib.util.spec_from_file_location("gh_pr_watch", MODULE_PATH)
watcher = importlib.util.module_from_spec(MODULE_SPEC)
assert MODULE_SPEC.loader is not None
MODULE_SPEC.loader.exec_module(watcher)

HERMES_CHECK_NAME = "hermes/pr-pipeline/code-review"
FIN_REVIEW_CHECK_NAME = "fin-review"


def check_run(
    name,
    conclusion,
    started,
    workflow="Hermes",
    status="COMPLETED",
    completed="",
):
    return {
        "__typename": "CheckRun",
        "name": name,
        "workflowName": workflow,
        "status": status,
        "conclusion": conclusion,
        "startedAt": started,
        "completedAt": completed,
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
            "name": HERMES_CHECK_NAME,
            "result": "pass",
            "conclusion": "SUCCESS",
        },
    }
    value.update(overrides)
    return value


def sample_snapshot(actions, **overrides):
    snapshot = {
        "pr": sample_pr(),
        "checks": sample_checks(),
        "fin_review": {
            "lgtm_for_head": False,
            "latest_lgtm": None,
            "new_items": [],
            "latest_request_at": None,
            "request_pending": False,
        },
        "actions": actions,
        "state_file": "/tmp/test-state.json",
    }
    snapshot.update(overrides)
    return snapshot


class CheckTests(unittest.TestCase):
    def test_normalizes_hermes_review_check(self):
        result = watcher.normalize_check(
            check_run("pr-pipeline / code-review", "SUCCESS", "2026-09-01T12:00:00Z")
        )
        self.assertEqual(result["name"], HERMES_CHECK_NAME)
        self.assertEqual(result["result"], "pass")

    def test_normalizes_fin_review_check(self):
        result = watcher.normalize_check(
            check_run(
                "fin review",
                "SUCCESS",
                "2026-09-01T12:00:00Z",
                workflow="",
            )
        )
        self.assertEqual(result["name"], FIN_REVIEW_CHECK_NAME)
        self.assertEqual(result["result"], "pass")

    def test_summarize_checks_recognizes_both_fin_review_check_names(self):
        hermes_summary = watcher.summarize_checks(
            [check_run("pr-pipeline / code-review", "SUCCESS", "2026-09-01T12:00:00Z")]
        )
        self.assertIsNotNone(hermes_summary["fin_review"])
        self.assertEqual(hermes_summary["fin_review"]["name"], HERMES_CHECK_NAME)

        fin_summary = watcher.summarize_checks(
            [
                check_run(
                    "fin review",
                    "SUCCESS",
                    "2026-09-01T12:00:00Z",
                    workflow="",
                )
            ]
        )
        self.assertIsNotNone(fin_summary["fin_review"])
        self.assertEqual(fin_summary["fin_review"]["name"], FIN_REVIEW_CHECK_NAME)

    def test_summarize_checks_prefers_substantive_fin_review_across_names(self):
        summary = watcher.summarize_checks(
            [
                check_run(
                    "pr-pipeline / code-review",
                    "SKIPPED",
                    "2026-09-01T12:05:00Z",
                ),
                check_run(
                    "fin review",
                    "SUCCESS",
                    "2026-09-01T12:00:00Z",
                    workflow="",
                ),
            ]
        )
        self.assertEqual(summary["fin_review"]["name"], FIN_REVIEW_CHECK_NAME)
        self.assertEqual(summary["fin_review"]["conclusion"], "SUCCESS")

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
                check_run(
                    "pr-pipeline / code-review", "FAILURE", "2026-09-01T12:00:00Z"
                ),
                check_run(
                    "pr-pipeline / code-review", "SKIPPED", "2026-09-01T12:05:00Z"
                ),
            ]
        )
        self.assertEqual(summary["fin_review"]["result"], "fail")

    def test_newer_substantive_check_wins(self):
        summary = watcher.summarize_checks(
            [
                check_run(
                    "pr-pipeline / code-review", "FAILURE", "2026-09-01T12:00:00Z"
                ),
                check_run(
                    "pr-pipeline / code-review", "SUCCESS", "2026-09-01T12:05:00Z"
                ),
            ]
        )
        self.assertEqual(summary["fin_review"]["result"], "pass")

    def test_queued_check_without_timestamp_supersedes_completed_check(self):
        summary = watcher.summarize_checks(
            [
                check_run(
                    "fin review",
                    "SUCCESS",
                    "2026-09-01T12:00:00Z",
                    workflow="",
                ),
                check_run(
                    "fin review",
                    "",
                    "",
                    workflow="",
                    status="QUEUED",
                ),
            ]
        )
        self.assertEqual(summary["fin_review"]["result"], "pending")


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
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "abc",
            "reviews": [],
        }
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

    def test_github_actions_lgtm_for_head_is_recognized(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "abc",
            "reviews": [
                {
                    "id": "review-1",
                    "author": {"login": "github-actions"},
                    "body": "LGTM ✅",
                    "submittedAt": "2026-09-01T12:00:00Z",
                    "commit": {"oid": "abc"},
                }
            ],
        }
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {})
        self.assertTrue(result["lgtm_for_head"])

    def test_recent_fin_review_comment_marks_request_pending(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "sha2",
            "reviews": [],
            "commits": [
                {"oid": "sha2", "committedDate": "2026-09-01T12:00:00Z"},
            ],
            "comments": [
                {"body": "fin review", "createdAt": "2026-09-01T12:00:05Z"},
            ],
        }
        now = watcher.parse_timestamp("2026-09-01T12:00:20Z")
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {}, fin_check=None, now=now)
        self.assertTrue(result["request_pending"])
        self.assertEqual(result["latest_request_at"], "2026-09-01T12:00:05Z")

    def test_fin_review_comment_before_head_commit_is_not_pending(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "sha2",
            "reviews": [],
            "commits": [
                {"oid": "sha1", "committedDate": "2026-09-01T11:59:00Z"},
                {"oid": "sha2", "committedDate": "2026-09-01T12:00:10Z"},
            ],
            "comments": [
                {"body": "fin review", "createdAt": "2026-09-01T12:00:05Z"},
            ],
        }
        now = watcher.parse_timestamp("2026-09-01T12:00:20Z")
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {}, fin_check=None, now=now)
        self.assertFalse(result["request_pending"])

    def test_fin_review_comment_expires_after_grace_window(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "sha2",
            "reviews": [],
            "commits": [
                {"oid": "sha2", "committedDate": "2026-09-01T12:00:00Z"},
            ],
            "comments": [
                {"body": "fin review", "createdAt": "2026-09-01T12:00:05Z"},
            ],
        }
        now = watcher.parse_timestamp("2026-09-01T12:03:00Z")
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {}, fin_check=None, now=now)
        self.assertFalse(result["request_pending"])

    def test_fin_review_comment_after_older_completed_check_is_pending(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "sha1",
            "reviews": [],
            "commits": [
                {"oid": "sha1", "committedDate": "2026-09-01T11:50:00Z"},
            ],
            "comments": [
                {"body": "fin review", "createdAt": "2026-09-01T12:02:00Z"},
            ],
        }
        old_check = {
            "name": FIN_REVIEW_CHECK_NAME,
            "result": "pass",
            "conclusion": "SUCCESS",
            "timestamp": "2026-09-01T11:55:00Z",
            "completed_at": "2026-09-01T11:56:00Z",
        }
        now = watcher.parse_timestamp("2026-09-01T12:02:10Z")
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {}, fin_check=old_check, now=now)
        self.assertTrue(result["request_pending"])

    def test_fin_review_comment_not_pending_once_check_or_response_arrives(self):
        pr = {
            "number": 1,
            "repo": "fintoc-com/example",
            "head_sha": "sha1",
            "reviews": [],
            "commits": [
                {"oid": "sha1", "committedDate": "2026-09-01T11:50:00Z"},
            ],
            "comments": [
                {"body": "fin review", "createdAt": "2026-09-01T12:02:00Z"},
            ],
        }
        new_check = {
            "name": FIN_REVIEW_CHECK_NAME,
            "result": "pass",
            "conclusion": "SUCCESS",
            "timestamp": "2026-09-01T12:02:05Z",
            "completed_at": "2026-09-01T12:02:40Z",
        }
        now = watcher.parse_timestamp("2026-09-01T12:02:45Z")
        with patch.object(watcher, "gh_api_list_paginated", return_value=[]):
            result = watcher.fetch_fin_review(pr, {}, fin_check=new_check, now=now)
        self.assertFalse(result["request_pending"])


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

    def test_draft_with_pending_fin_review_request_waits(self):
        checks = sample_checks(fin_review=None)
        actions = watcher.recommend_actions(
            sample_pr(is_draft=True),
            checks,
            {"lgtm_for_head": False, "new_items": [], "request_pending": True},
        )
        self.assertEqual(actions, ["wait_for_fin_review"])

    def test_draft_with_old_skipped_check_and_pending_request_waits(self):
        checks = sample_checks(
            fin_review={
                "name": HERMES_CHECK_NAME,
                "result": "pass",
                "conclusion": "SKIPPED",
            }
        )
        actions = watcher.recommend_actions(
            sample_pr(is_draft=True),
            checks,
            {"lgtm_for_head": False, "new_items": [], "request_pending": True},
        )
        self.assertEqual(actions, ["wait_for_fin_review"])

    def test_same_sha_re_request_after_success_without_lgtm_waits(self):
        checks = sample_checks(
            fin_review={
                "name": FIN_REVIEW_CHECK_NAME,
                "result": "pass",
                "conclusion": "SUCCESS",
            }
        )
        actions = watcher.recommend_actions(
            sample_pr(),
            checks,
            {"lgtm_for_head": False, "new_items": [], "request_pending": True},
        )
        self.assertEqual(actions, ["wait_for_fin_review"])

    def test_fin_review_success_with_inline_findings_without_lgtm(self):
        checks = sample_checks(
            fin_review={
                "name": FIN_REVIEW_CHECK_NAME,
                "result": "pass",
                "conclusion": "SUCCESS",
            }
        )
        review = {
            "lgtm_for_head": False,
            "new_items": [{"kind": "review_comment", "id": "42"}],
        }
        actions = watcher.recommend_actions(sample_pr(), checks, review)
        self.assertEqual(actions, ["process_fin_review_findings"])

    def test_failed_fin_review_check_is_not_generic_ci_failure(self):
        failed_fin = {
            "name": FIN_REVIEW_CHECK_NAME,
            "result": "fail",
            "conclusion": "FAILURE",
        }
        checks = sample_checks(
            all_passing=False,
            failed_count=1,
            failed=[failed_fin],
            fin_review=failed_fin,
        )
        actions = watcher.recommend_actions(
            sample_pr(), checks, {"lgtm_for_head": False, "new_items": []}
        )
        self.assertEqual(actions, ["inspect_or_rerun_fin_review"])

    def test_lgtm_for_head_while_ci_pending_only_waits_for_checks(self):
        checks = sample_checks(
            all_passing=False,
            pending_count=1,
            pending=[{"name": "ci/tests", "result": "pending"}],
            fin_review=None,
        )
        actions = watcher.recommend_actions(
            sample_pr(is_draft=True),
            checks,
            {"lgtm_for_head": True, "new_items": []},
        )
        self.assertEqual(actions, ["wait_for_checks"])

    def test_skipped_review_check_is_ready_with_lgtm(self):
        checks = sample_checks(
            fin_review={
                "name": HERMES_CHECK_NAME,
                "result": "pass",
                "conclusion": "SKIPPED",
            }
        )
        actions = watcher.recommend_actions(
            sample_pr(), checks, {"lgtm_for_head": True, "new_items": []}
        )
        self.assertEqual(actions, ["ready_for_review"])

    def test_draft_with_skipped_review_reports_unavailable_after_ci(self):
        checks = sample_checks(
            fin_review={
                "name": HERMES_CHECK_NAME,
                "result": "pass",
                "conclusion": "SKIPPED",
            }
        )
        actions = watcher.recommend_actions(
            sample_pr(is_draft=True), checks, {"lgtm_for_head": False, "new_items": []}
        )
        self.assertEqual(actions, ["report_fin_review_unavailable"])

    def test_draft_with_unavailable_review_still_waits_for_ci(self):
        pending = [{"name": "ci/tests", "result": "pending"}]
        checks = sample_checks(
            all_passing=False,
            pending_count=1,
            pending=pending,
            fin_review={
                "name": HERMES_CHECK_NAME,
                "result": "pass",
                "conclusion": "SKIPPED",
            },
        )
        actions = watcher.recommend_actions(
            sample_pr(is_draft=True), checks, {"lgtm_for_head": False, "new_items": []}
        )
        self.assertEqual(actions, ["wait_for_checks"])

    def test_review_findings_precede_generic_ci_failure(self):
        failed = [
            {"name": HERMES_CHECK_NAME, "result": "fail"},
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
        self.assertEqual(
            actions, ["process_fin_review_findings", "diagnose_ci_failure"]
        )


class WatchLoopTests(unittest.TestCase):
    def run_watch_with_snapshots(self, snapshots, poll_seconds=15):
        args = types.SimpleNamespace(poll_seconds=poll_seconds)
        stdout = io.StringIO()
        with (
            patch.object(watcher, "collect_snapshot", side_effect=snapshots),
            patch.object(watcher.time, "sleep") as sleep_mock,
            redirect_stdout(stdout),
        ):
            code = watcher.run_watch(args)
        events = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
        return code, events, sleep_mock

    def test_watch_polls_through_wait_actions_and_exits_on_actionable_event(self):
        snapshots = [
            sample_snapshot(["wait_for_fin_review", "wait_for_checks"]),
            sample_snapshot(["wait_for_checks"]),
            sample_snapshot(["process_fin_review_findings", "wait_for_checks"]),
        ]
        code, events, sleep_mock = self.run_watch_with_snapshots(snapshots)
        self.assertEqual(code, 0)
        self.assertEqual(sleep_mock.call_count, 2)
        sleep_mock.assert_called_with(15)
        self.assertEqual(
            [event["event"] for event in events],
            ["snapshot", "snapshot", "snapshot", "stop"],
        )
        self.assertEqual(
            events[-1]["actions"], ["process_fin_review_findings", "wait_for_checks"]
        )

    def test_watch_exits_on_every_actionable_action(self):
        actionable_cases = [
            ["process_fin_review_findings"],
            ["diagnose_ci_failure"],
            ["inspect_or_rerun_fin_review"],
            ["request_fin_review"],
            ["ready_for_review"],
            ["report_fin_review_unavailable"],
            ["stop_pr_closed"],
        ]
        for actions in actionable_cases:
            with self.subTest(actions=actions):
                code, events, sleep_mock = self.run_watch_with_snapshots(
                    [sample_snapshot(actions)]
                )
                self.assertEqual(code, 0)
                self.assertEqual(sleep_mock.call_count, 0)
                self.assertEqual(
                    [event["event"] for event in events], ["snapshot", "stop"]
                )
                self.assertEqual(events[-1]["actions"], actions)

    def test_collect_snapshot_handles_draft_comment_race_and_omits_raw_lists(self):
        pr_payload = {
            "number": 22534,
            "url": "https://github.com/fintoc-com/fintoc-rails/pull/22534",
            "repo": "fintoc-com/fintoc-rails",
            "head_sha": "sha2",
            "head_branch": "feat/example",
            "is_draft": True,
            "state": "OPEN",
            "closed": False,
            "checks": [status_context("ci/tests", "PENDING")],
            "reviews": [],
            "comments": [
                {"body": "fin review", "createdAt": "2026-09-01T12:00:05Z"},
            ],
            "commits": [
                {"oid": "sha2", "committedDate": "2026-09-01T12:00:00Z"},
            ],
        }
        now = watcher.parse_timestamp("2026-09-01T12:00:15Z")
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = str(Path(tmpdir) / "state.json")
            args = types.SimpleNamespace(
                pr="22534",
                repo="fintoc-com/fintoc-rails",
                state_file=state_file,
            )
            with (
                patch.object(watcher, "resolve_pr", return_value=dict(pr_payload)),
                patch.object(watcher, "gh_api_list_paginated", return_value=[]),
                patch.object(watcher.time, "time", return_value=now),
            ):
                snapshot = watcher.collect_snapshot(args)
        self.assertEqual(
            snapshot["actions"], ["wait_for_fin_review", "wait_for_checks"]
        )
        self.assertTrue(snapshot["fin_review"]["request_pending"])
        self.assertNotIn("comments", snapshot["pr"])
        self.assertNotIn("commits", snapshot["pr"])


if __name__ == "__main__":
    unittest.main()
