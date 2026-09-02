#!/usr/bin/env python3
"""Watch a GitHub PR until checks pass and fin-review approves the head SHA."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

IGNORED_CHECKS = {"bors", "hermes/approval-gate"}
FIN_REVIEW_CHECK = "hermes/pr-pipeline/code-review"
FIN_REVIEW_LOGIN = "fin-review"
PENDING_STATES = {"EXPECTED", "IN_PROGRESS", "PENDING", "QUEUED", "REQUESTED", "WAITING"}
PASSING_CONCLUSIONS = {"NEUTRAL", "SKIPPED", "SUCCESS"}


class GhCommandError(RuntimeError):
    pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Watch a PR until checks pass and fin-review approves it"
    )
    parser.add_argument("--pr", default="auto", help="auto, PR number, or PR URL")
    parser.add_argument("--repo", help="Optional OWNER/REPO override")
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--state-file", help="Path to state JSON file")
    parser.add_argument("--once", action="store_true", help="Emit one snapshot")
    parser.add_argument("--watch", action="store_true", help="Emit JSONL snapshots until ready")
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be > 0")
    if args.once and args.watch:
        parser.error("--once and --watch are mutually exclusive")
    if not args.once and not args.watch:
        args.once = True
    return args


def gh_text(args, repo=None):
    cmd = ["gh"]
    if repo and (not args or args[0] != "api"):
        cmd.extend(["-R", repo])
    cmd.extend(args)
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as err:
        raise GhCommandError("`gh` command not found") from err
    except subprocess.CalledProcessError as err:
        details = (err.stderr or err.stdout or "").strip()
        raise GhCommandError(f"GitHub CLI command failed: {' '.join(cmd)}\n{details}") from err
    return proc.stdout


def gh_json(args, repo=None):
    raw = gh_text(args, repo=repo).strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise GhCommandError(f"Invalid JSON from: gh {' '.join(args)}") from err


def parse_pr_spec(pr_spec):
    if pr_spec == "auto":
        return None
    if re.fullmatch(r"\d+", pr_spec):
        return pr_spec
    parsed = urlparse(pr_spec)
    if parsed.scheme and parsed.netloc and "/pull/" in parsed.path:
        return pr_spec
    raise ValueError("--pr must be 'auto', a PR number, or a PR URL")


def extract_repo(pr_url):
    parts = [part for part in urlparse(pr_url).path.split("/") if part]
    if len(parts) >= 4 and parts[2] == "pull":
        return f"{parts[0]}/{parts[1]}"
    return None


def resolve_pr(pr_spec, repo_override=None):
    target = parse_pr_spec(pr_spec)
    cmd = ["pr", "view"]
    if target:
        cmd.append(target)
    cmd.extend(
        [
            "--json",
            "number,url,state,isDraft,mergedAt,closedAt,headRefName,headRefOid,statusCheckRollup,reviews",
        ]
    )
    data = gh_json(cmd, repo=repo_override)
    if not isinstance(data, dict):
        raise GhCommandError("Unexpected payload from `gh pr view`")
    repo = repo_override or extract_repo(str(data.get("url") or ""))
    if not repo:
        raise GhCommandError("Unable to determine OWNER/REPO")
    state = str(data.get("state") or "").upper()
    return {
        "number": int(data["number"]),
        "url": str(data.get("url") or ""),
        "repo": repo,
        "head_sha": str(data.get("headRefOid") or ""),
        "head_branch": str(data.get("headRefName") or ""),
        "is_draft": bool(data.get("isDraft")),
        "state": state,
        "closed": bool(data.get("closedAt")) or bool(data.get("mergedAt")) or state != "OPEN",
        "checks": data.get("statusCheckRollup") or [],
        "reviews": data.get("reviews") or [],
    }


def normalize_name(value):
    value = re.sub(r"\s*/\s*", "/", str(value or "").strip().lower())
    return re.sub(r"\s+", "-", value)


def normalize_check(raw):
    kind = str(raw.get("__typename") or "")
    if kind == "StatusContext" or "context" in raw:
        name = normalize_name(raw.get("context"))
        state = str(raw.get("state") or "").upper()
        timestamp = str(raw.get("startedAt") or "")
        url = str(raw.get("targetUrl") or "")
        if state in PENDING_STATES:
            result = "pending"
        elif state == "SUCCESS":
            result = "pass"
        else:
            result = "fail"
        conclusion = state
    else:
        job = normalize_name(raw.get("name"))
        workflow = normalize_name(raw.get("workflowName"))
        name = f"{workflow}/{job}" if workflow else job
        status = str(raw.get("status") or "").upper()
        conclusion = str(raw.get("conclusion") or "").upper()
        timestamp = str(raw.get("startedAt") or raw.get("completedAt") or "")
        url = str(raw.get("detailsUrl") or "")
        if status != "COMPLETED" or not conclusion:
            result = "pending"
        elif conclusion in PASSING_CONCLUSIONS:
            result = "pass"
        else:
            result = "fail"
    return {
        "name": name,
        "result": result,
        "ignored": name in IGNORED_CHECKS,
        "conclusion": conclusion,
        "timestamp": timestamp,
        "url": url,
    }


def latest_checks(raw_checks):
    latest = {}
    for raw in raw_checks:
        if not isinstance(raw, dict):
            continue
        check = normalize_check(raw)
        previous = latest.get(check["name"])
        if previous is None:
            latest[check["name"]] = check
            continue
        # Comment-triggered Hermes runs add SKIPPED duplicates. A skipped run
        # does not supersede a substantive run for the same job and SHA.
        previous_skipped = previous["conclusion"] == "SKIPPED"
        current_skipped = check["conclusion"] == "SKIPPED"
        if current_skipped and not previous_skipped:
            continue
        if previous_skipped and not current_skipped:
            latest[check["name"]] = check
            continue
        if check["timestamp"] >= previous["timestamp"]:
            latest[check["name"]] = check
    return sorted(latest.values(), key=lambda item: item["name"])


def summarize_checks(raw_checks):
    checks = latest_checks(raw_checks)
    active = [check for check in checks if not check["ignored"]]
    pending = [check for check in active if check["result"] == "pending"]
    failed = [check for check in active if check["result"] == "fail"]
    passed = [check for check in active if check["result"] == "pass"]
    ignored = [check for check in checks if check["ignored"]]
    fin_review = next((check for check in checks if check["name"] == FIN_REVIEW_CHECK), None)
    return {
        "all_passing": not pending and not failed,
        "pending_count": len(pending),
        "failed_count": len(failed),
        "passed_count": len(passed),
        "ignored_count": len(ignored),
        "pending": pending,
        "failed": failed,
        "ignored": ignored,
        "fin_review": fin_review,
    }


def gh_api_list_paginated(endpoint):
    items = []
    page = 1
    while True:
        separator = "&" if "?" in endpoint else "?"
        data = gh_json(["api", f"{endpoint}{separator}page={page}"])
        if data is None:
            break
        if not isinstance(data, list):
            raise GhCommandError(f"Unexpected list payload from {endpoint}")
        items.extend(data)
        if len(data) < 100:
            break
        page += 1
    return items


def reviewer_login(author):
    if isinstance(author, dict):
        login = author.get("login") or ""
    else:
        login = author or ""
    return str(login).lower().removesuffix("[bot]")


def normalize_review(review):
    commit = review.get("commit")
    if isinstance(commit, dict):
        commit_sha = commit.get("oid") or ""
    else:
        commit_sha = review.get("commit_id") or ""
    return {
        "kind": "review",
        "id": str(review.get("id") or ""),
        "author": reviewer_login(review.get("author") or review.get("user")),
        "body": str(review.get("body") or ""),
        "commit_sha": str(commit_sha),
        "created_at": str(review.get("submittedAt") or review.get("submitted_at") or ""),
        "url": str(review.get("html_url") or ""),
    }


def normalize_review_comment(comment):
    return {
        "kind": "review_comment",
        "id": str(comment.get("id") or ""),
        "node_id": str(comment.get("node_id") or ""),
        "review_id": str(comment.get("pull_request_review_id") or ""),
        "author": reviewer_login(comment.get("user")),
        "body": str(comment.get("body") or ""),
        "path": comment.get("path"),
        "line": comment.get("line") or comment.get("original_line"),
        "created_at": str(comment.get("created_at") or ""),
        "url": str(comment.get("html_url") or ""),
    }


def fetch_fin_review(pr, state):
    comments = gh_api_list_paginated(
        f"repos/{pr['repo']}/pulls/{pr['number']}/comments?per_page=100"
    )
    review_comments = [
        normalize_review_comment(item)
        for item in comments
        if isinstance(item, dict) and reviewer_login(item.get("user")) == FIN_REVIEW_LOGIN
    ]
    reviews = [
        normalize_review(item)
        for item in pr["reviews"]
        if isinstance(item, dict)
        and reviewer_login(item.get("author") or item.get("user")) == FIN_REVIEW_LOGIN
    ]
    seen = {str(item) for item in state.get("seen_fin_review_item_ids") or []}
    new_items = []
    for item in review_comments + reviews:
        if not item["id"] or item["id"] in seen or not item["body"].strip():
            continue
        new_items.append(item)
        seen.add(item["id"])
    new_items.sort(key=lambda item: (item["created_at"], item["kind"], item["id"]))
    state["seen_fin_review_item_ids"] = sorted(seen)
    lgtm_reviews = [
        review
        for review in reviews
        if review["commit_sha"] == pr["head_sha"] and "lgtm" in review["body"].lower()
    ]
    return {
        "lgtm_for_head": bool(lgtm_reviews),
        "latest_lgtm": lgtm_reviews[-1] if lgtm_reviews else None,
        "new_items": new_items,
    }


def load_state(path):
    if not path.exists():
        return {"seen_fin_review_item_ids": []}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as err:
        raise RuntimeError(f"State file is not valid JSON: {path}") from err
    if not isinstance(data, dict):
        raise RuntimeError(f"State file must contain an object: {path}")
    return data


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f"{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def default_state_file(pr):
    repo = pr["repo"].replace("/", "-")
    return Path(f"/tmp/babysit-pr-{repo}-{pr['number']}.json")


def recommend_actions(pr, checks, fin_review):
    if pr["closed"]:
        return ["stop_pr_closed"]
    fin_check = checks["fin_review"]
    fin_check_passed = (
        fin_check is not None
        and fin_check["result"] == "pass"
        and fin_check["conclusion"] == "SUCCESS"
    )
    if checks["all_passing"] and fin_check_passed and fin_review["lgtm_for_head"]:
        return ["ready_for_review"]

    actions = []
    findings = [
        item for item in fin_review["new_items"] if item["kind"] == "review_comment"
    ]
    if findings:
        actions.append("process_fin_review_findings")

    generic_failures = [
        check for check in checks["failed"] if check["name"] != FIN_REVIEW_CHECK
    ]
    if generic_failures:
        actions.append("diagnose_ci_failure")

    if fin_check is None:
        actions.append("request_fin_review" if pr["is_draft"] else "wait_for_fin_review")
    elif fin_check["result"] == "pending":
        actions.append("wait_for_fin_review")
    elif fin_check["result"] == "fail" and not findings:
        actions.append("inspect_or_rerun_fin_review")
    elif not fin_check_passed and not findings:
        actions.append("request_fin_review")
    elif not fin_review["lgtm_for_head"] and not findings:
        actions.append("request_fin_review")

    if checks["pending_count"] and "wait_for_checks" not in actions:
        actions.append("wait_for_checks")
    if not actions:
        actions.append("wait_for_fin_review")
    return actions


def collect_snapshot(args):
    pr = resolve_pr(args.pr, repo_override=args.repo)
    state_path = Path(args.state_file) if args.state_file else default_state_file(pr)
    state = load_state(state_path)
    if state.get("head_sha") != pr["head_sha"]:
        state["head_sha"] = pr["head_sha"]
    checks = summarize_checks(pr.pop("checks"))
    fin_review = fetch_fin_review(pr, state)
    actions = recommend_actions(pr, checks, fin_review)
    state["last_snapshot_at"] = int(time.time())
    save_state(state_path, state)
    return {
        "pr": pr,
        "checks": checks,
        "fin_review": fin_review,
        "actions": actions,
        "state_file": str(state_path),
    }


def print_json(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def snapshot_key(snapshot):
    return (
        snapshot["pr"]["head_sha"],
        snapshot["pr"]["is_draft"],
        snapshot["checks"]["pending_count"],
        snapshot["checks"]["failed_count"],
        snapshot["checks"]["passed_count"],
        snapshot["fin_review"]["lgtm_for_head"],
        tuple(snapshot["actions"]),
        tuple(item["id"] for item in snapshot["fin_review"]["new_items"]),
    )


def run_watch(args):
    previous = None
    while True:
        snapshot = collect_snapshot(args)
        current = snapshot_key(snapshot)
        print_json({"event": "snapshot", "changed": current != previous, "payload": snapshot})
        if "ready_for_review" in snapshot["actions"] or "stop_pr_closed" in snapshot["actions"]:
            print_json({"event": "stop", "actions": snapshot["actions"], "pr": snapshot["pr"]})
            return 0
        previous = current
        time.sleep(args.poll_seconds)


def main():
    args = parse_args()
    try:
        if args.watch:
            return run_watch(args)
        print_json(collect_snapshot(args))
        return 0
    except (GhCommandError, RuntimeError, ValueError) as err:
        print(f"gh_pr_watch.py error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("gh_pr_watch.py interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
