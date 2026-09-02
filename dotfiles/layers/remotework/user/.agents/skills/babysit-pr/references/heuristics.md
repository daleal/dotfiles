# CI and Review Heuristics

## CI failures

Treat a failure as branch-related when logs identify changed code, deterministic tests in changed areas, compile/type/lint errors, snapshots caused by the PR, or configuration modified by the PR.

Treat it as transient or unrelated when logs identify runner provisioning, network/registry outages, service rate limits, GitHub Actions incidents, or known flaky tests outside the changed area.

Inspect evidence once before deciding. Fix branch regressions. Retry transient failures without changing code. Ask the user when ownership remains unclear or safe retries fail.

## fin-review findings

Fix a finding when it is technically correct, plausible in production, within the PR's intent, and solvable without disproportionate complexity or unrelated refactoring.

Decline a finding when it depends on an extremely unlikely scenario and addressing it would materially worsen readability, maintainability, performance, API design, or scope. Also decline incorrect or already-addressed findings.

Do not use rarity alone as a dismissal. Consider impact, probability, existing invariants, boundary ownership, and whether a small fix exists. Example dismissable comment: "If `window.href = '/'` fails, this code will break". A `window.href` assignment failure is so unlikely, that the risk is negligible.

Ignore `fin-review`'s proposed fix, only evaluate its findings. Decide the appropriate changes based on your own assessment. Remember, you have more context than the `fin-review` bot, so use your judgment to follow its advice.

When declining, reply with `[babysit] <justification>` and cite the relevant invariant or tradeoff. When fixing, reply with `[babysit] fixed in <commit>` and resolve the thread after the push succeeds.

## Roadblocks

Stop and ask the user when the worktree prevents safe editing, GitHub access or push fails, CI remains broken after safe retries, ownership is external, or feedback requires a product/design decision.
