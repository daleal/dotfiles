---
description: Propose a git commit plan
---

# Committing Staged Changes

Propose a git commit plan for all of the currently staged changes.

## Steps

1. Run `git diff --cached --stat` to see which files are staged. If nothing is staged, stop and tell the user.
2. Run `git diff --cached` to understand what actually changed.
3. Use this to write messages that explains WHY, not just WHAT.
4. Wait for user approval. If rejected, revise.
5. After committing, ask whether to push to the remote.

## Commit Rules

- Each commit should group logical changes.
- Each commit is expected to be reviewed in isolation by the team. Our **main goal** is to make it easy to review and understand each commit.
- Implementation and tests should always go in the same commit. Split by feature area, not by file type.
- Changes within a single file CAN and SHOULD be split across multiple commits if they address different concerns (e.g., two distinct fixes, a feature + a refactor, separate logical changes). Do NOT treat "same file" as a reason to group changes into one commit.
- Each commit must be self-consistent: do NOT reference props, functions, types, or APIs that are introduced in a later commit. If a file needs to be `git add`ed to allow for a self-consistent git commit plan, ask the user to stage it before proposing the commit plan.
- Commits should be written in English.
- Commits should look like:
  - A single, concise conventional-commit subject line: `<type>(<scope>): <description>` (common types: `feat`, `fix`, `refactor`, `test`, `docs`, `ci`, `chore`)
  - A body that explains WHY the change was made — e.g., what constraint forced the shape of the change, what prior commit this builds on, what the caller/consumer now needs. If the change follows from a previous refactor (e.g., a return type changed from query to array), say so explicitly.
- Do not include AI attribution in the commit.
- Commit using HEREDOC to preserve formatting.
- Terse. 1–2 short paragraphs in the body is usually enough
- If the change is a consequence of an earlier commit's shape change (e.g., a method now returns enum values instead of an AR relation), name that cause in the body

## Safety

- Only commit what is already staged — NEVER `git add` files on the user's behalf unless they approve adding them for self-consistency.
- NEVER push unless the user explicitly says to.
- NEVER amend existing commits unless asked.
