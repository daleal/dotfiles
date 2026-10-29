---
name: no-comments
description: Hunt down and delete code comments, flag the code they excuse, and encode real constraints instead of writing prose. Use before adding any code comment, and whenever asked to remove, clean up, review, audit or analyze code comments
---

# No comments

Comments are guilty until proven innocent. Narration, banners, commented-out code, workaround sermons, TODO alibis: delete them. When a comment exists to excuse confusing code, the code is the problem. Flag it.

## Before adding a comment

Don't. First try to make the comment unnecessary:

- Rename the variable, function or type so the name says it.
- Extract a well-named function or constant.
- Encode the constraint in a type, assertion, test or lint rule.
- Restructure so the behavior is obvious.

Write the comment only if it fits a keep exception below. Keep it to one or two lines that state the external fact, not a justification.

## Keep exceptions

The only comments allowed to survive:

- Legal or license headers.
- Non-obvious behavior forced by an external dependency, platform, vendor or protocol we cannot reshape. Surprises in our own code don't qualify: delete the comment and flag the symbol `MUST KILL` for a rename, extract, type or redesign that makes the behavior obvious without prose.
- Formatter directives like `// prettier-ignore`.
- Lint suppressions, but only when the rule is faulty, pedantic or style-only.
- Doc comments that define a public API contract.
- Issue or RFC links that explain a constraint code cannot express.

If you're not sure an exception applies, delete the comment.

## Suppressions

`eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `# noqa`, `# type: ignore`, `rubocop:disable` and the like are suspicious. Look up the rule. If it catches real bugs or protects correctness or safety, delete the suppression and flag the guilty symbol `MUST KILL`.

## Defensive comments

`IMPORTANT`, `do not remove`, `do not change wording`, `talk to X before changing`, `too risky`, `fine for now` and long justifications are a hint, not proof. Read the nearby code. If the claim isn't obvious there, use the `how` and/or `why` skills on the named symbol or call.

- Keep it only if it's a foreign, keep-list constraint that is proven true today on a live path.
- Our-code surprises: delete and flag `MUST KILL`.
- Still unsure after investigating: delete.
- Don't rewrite a guilty comment into a shorter excuse.

For real constraints we control, offer the cheapest in-scope encoding (type, runtime check, test or CI lint). Ask the user before adding it. If approved, encode it, then delete the comment. Otherwise delete the comment and report the constraint as open.

## Removing or analyzing comments

### Scope

Use the files or diff the user gives you. Otherwise use the current diff against the base branch (default `main`), including the working tree. Never touch anything outside the scope.

### Steps

1. Read every comment and suppression in scope. Judge each against the keep exceptions, suppression rules and defensive-comment rules above.
2. If asked to analyze only, stop and report. Otherwise delete every comment that doesn't qualify.
3. For each `MUST KILL`, name the exact symbol in scope and give a one-line reason. Every flag must be true. Don't invent findings.
4. Fix trivial flags directly: delete a dead path, drop an unused parameter, call the real API. If a fix needs a redesign, sketch it and ask before implementing.
5. Fix root causes, never add guards around symptoms. If the root cause is outside scope, make the smallest in-scope fix and report the rest as open.

### Report

- Files touched and deletion count.
- Comments kept, each with its exception.
- `MUST KILL` flags, one line each, and which were fixed.
- Encoding offers and any encodings added.
- Unenforced constraints and other open work.
