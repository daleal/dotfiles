---
name: babysit-pr
description: Babysits a Pull Request until it is ready for human review. Use when asked to "babysit" a PR, "monitor", "watch", "get a PR ready for review", "get a PR out of draft" or "keep checks green".
---

# PR Babysitter

## Objective

Babysit the current PR until all non-ignored checks pass and `fin-review` says `LGTM` for the latest commit. If the PR is a draft, then mark it ready for review and stop.

This skill prepares a PR for human review. It does not wait for human approval or merging, handle merge conflicts, invoke Bors, or merge the PR.

## Inputs

Accept no argument (infer the PR from the current branch), a PR number, or a PR URL.

## Workflow

1. Verify that the current branch is the PR head branch and inspect the PR directly with `gh` before making changes.
2. If the PR is a draft, comment `fin review` once to start the AI review. After a babysitter push, repeat it only if the earlier comment successfully started a review.
3. Start the watcher in continuous mode and consume its JSONL output in the current session.
4. Wait for checks to finish after every push. Never assess readiness from checks belonging to an older SHA.
5. Ignore `hermes/approval-gate` and `bors`; they do not need to pass for babysitting to succeed.
6. Diagnose any other failed check. Fix failures caused by the branch, commit, push, trigger draft review if needed, and resume watching the new SHA.
7. Watch `Hermes/pr-pipeline/code-review` specifically. Let it finish before inspecting newly published `fin-review` feedback.
8. Evaluate each `fin-review` finding. Fix correct, useful findings; reject speculative edge cases when the added complexity or degraded design outweighs their practical benefit.
  - The `fin-review` bot might propose a fix for a finding. You should ignore its proposed fix, and only evaluate the comment. If something needs to be changed, decide yourself how to fix it.
  - Remember, you have more context than the `fin-review` bot, so use your judgment to follow its advice.
9. After handling findings, run `fin review` again when no push retriggers review. On ready-for-review PRs, each push triggers review automatically. On draft PRs, explicitly comment `fin review` after every push.
10. Continue until the latest SHA has an `LGTM` from `fin-review` and every non-ignored check passes.
11. If the PR is still a draft, run `gh pr ready`. Report the successful handoff and stop.

If `fin review` leaves the draft's code-review check `SKIPPED` and publishes no review or findings, the comment trigger is unavailable. Do not retry it and do not mark the PR ready. Continue fixing and waiting for every other check, then report the comment-trigger problem with the PR left as a draft.

Do not stop after a push, while checks are pending, after merely replying to review feedback, or when an older commit has an `LGTM`.

## Commands

```bash
# One-shot diagnostic
python3 scripts/gh_pr_watch.py --pr auto --once

# Continuous watch
python3 scripts/gh_pr_watch.py --pr auto --watch

# Trigger fin-review
gh pr comment <pr> --body 'fin review'

# Mark a successful draft ready for human review
gh pr ready <pr>
```

Pass `-R <owner/repo>` to `gh` when the current checkout does not identify the target repository.

## Check Handling

The watcher normalizes duplicate check runs and keeps only the newest result for each check name. This matters because comment-triggered Hermes runs can create several `pr-pipeline / code-review` entries for one SHA.

Ignored checks:

- `hermes/approval-gate`: may wait for human approval.
- `bors`: never passes before the merge flow starts.

All other checks must be terminal and non-failing. `SKIPPED` and `NEUTRAL` are acceptable. For a failure:

1. Inspect the failed job and logs.
2. Fix it only when evidence connects it to the PR branch.
3. Push the fix and wait for the complete check set on the new SHA.
4. For transient infrastructure failures, rerun the failed job if safe. Ask the user when retries are exhausted or ownership is unclear.

Read `references/heuristics.md` before deciding whether to fix or reject a finding.

## Fin Review

`fin-review[bot]` publishes inline review comments and a review result. In some repositories its LGTM review is attributed to `github-actions`; accept either identity when the review targets the current head SHA. Its Hermes check is normalized as `hermes/pr-pipeline/code-review`.

When the check is pending, wait. When it fails, inspect the newly surfaced `fin-review` comments before doing anything else.

For each finding:

- If fixing it improves the code, make the smallest correct change, commit, and push. Reply to the thread with `[babysit] fixed in <commit>`, then resolve it.
- If it is not worth fixing, reply with `[babysit] <justification>`. Give a concrete technical justification. Do not resolve that thread unless explicitly asked.
- Do not blindly implement hypothetical edge-case defenses that add substantial complexity, weaken the design, or lack a plausible production scenario.

After all findings are handled, obtain a fresh review for the current SHA. A prior `LGTM` is stale after any push.

On draft PRs, post `fin review` after every push only while that trigger is known to work. On non-draft PRs, a push automatically starts review; use `fin review` only when another review is needed without a push, such as after rejecting a finding.

The PR is successfully babysat only when the current SHA has `fin-review` feedback containing `LGTM` and all non-ignored checks pass.

## GitHub Writes

The user authorizes these writes while babysitting:

- Push fixes to the PR head branch.
- Comment `fin review` to trigger the reviewer.
- Reply to `fin-review` findings using the exact `[babysit]` prefix.
- Resolve `fin-review` threads for findings fixed in code.
- Mark a successfully babysat draft PR ready for review.

Do not reply to or resolve human review comments without explicit user approval. Do not merge, close, reopen, or convert a ready PR back to draft.

Read `references/github-api-notes.md` for reply and thread-resolution commands.

## Git Safety

- Work only on the PR head branch.
- Avoid destructive git commands.
- Before editing, stop if unrelated uncommitted changes make a safe fix uncertain.
- Commit and push each coherent fix, then resume monitoring immediately.
- Keep only one watcher process active for a PR.

## Roadblocks

Stop and ask the user what to do when:

- The worktree has conflicting unrelated changes.
- `gh` authentication or permissions fail.
- The PR branch cannot be pushed.
- CI failures persist after safe retries.
- A failure appears owned by infrastructure or another team.
- Reviewer feedback is ambiguous or requires a product/design decision.
- A human review comment needs a response.

An unavailable `fin review` comment trigger is not an immediate roadblock: finish all other branch-owned fixes and checks first, leave the PR in draft, then report it.

Include the concrete roadblock, evidence gathered, and the smallest useful choices available.

## Output

During monitoring, report only status changes and occasional concise heartbeats. On success report the PR URL, and its final state (ready for review, checks passing, AI reviewer LGTM, etc).

## References

- Decision criteria: `references/heuristics.md`
- GitHub CLI/API commands: `references/github-api-notes.md`
