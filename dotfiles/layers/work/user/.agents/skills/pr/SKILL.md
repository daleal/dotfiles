---
name: pr
description: Creates a PR (Pull Request). Load when you need to create a PR and you have ALREADY made all the code changes, created the feature branch and made the necessary commits.
---

## Linear Issue

Use the Linear tools to interact with Linear.

PRs need to match a Linear issue. If the user specified a Linear issue to use, you should use that. If the user
mentions the issue already exists but doesn't mention which one it is, you should search for it. If the user
doesn't mention Linear at all, you should create a new Linear issue to use (create it with status "in progress").
Match the issue to the correct team based on the code changes.

## Pull Request

Create the PR as a draft. Assign me (the CLI user) to the PR. Use the `gh` CLI to interact with GitHub.

### Title

The title of the PR should be brief, and should summarize the content of the PR. It should also start with the
id of the Linear issue (previously created/obtained) in brackets.
An example could be: `[INT-1234] Use antialiased font smoothing to match Figma`

### Body

The body of the PR should be a brief explanation IN MILD CHILEAN SPANISH that a human should be able to
use as context to then read the PR and evaluate the code critically, without missing information.
It should be as brief as possible while aiming to give the reviewer the tools it might need to review the
PR appropriately. You should use the following "template" for the body:

```md
## Contexto

## Qué hay de nuevo?

## Demo

## Tests

Tests unitarios

## Consideraciones

## Rollback
¿Es seguro hacer rollback? Sí/No
¿Cuáles son los pasos para hacer rollback?
```

Literally write "Tests unitarios", no need to describe every test you added/changed.

#### Qué hay de nuevo?

Make this section as visual as possible. Read [references/visual-outline.md](references/visual-outline.md) and
build a compact structural view of the change (pseudocode, call trees, component trees, file trees, SQL/contract
diffs, Mermaid) instead of prose. Read the complete diff and enough surrounding code to get the shapes right.

#### Demo

Optional. Include it only if visual assets worth showing (screenshots, recordings, GIFs) were generated during the
session, e.g. with a browser tool. Pick only the ones that help the reviewer see the change (before/after, new UI
states, the fixed bug); skip redundant or intermediate captures. Never generate new assets just for this section.
Omit the section entirely if there are none.

Reference each asset in the body by its local path with a short caption, e.g. `![Estado de error del login](./login.png)`,
and pass every file with `--attach` to `gh pr create` (or `gh pr edit`). `gh` uploads them and rewrites the
references to the uploaded URLs. Videos render as a player and take no alt text. If an upload fails, the PR is still
created but `gh` exits non-zero: check the body and tell the user which assets are missing.

#### Guardrails

- DO NOT use additional sections.
- You do NOT need to list ALL of the changes on the PR body, just a summary of the most important ones, and any context that might be needed to understand the PR. The commits and code are there for the reviewer to check the details.
- If no considerations apply, you can skip that section. Same for Demo when there are no assets.
- The rollback section should be filled only if executing a rollback might prove challenging for some reason (for example, a difficult data migration that cannot easily be rollbacked). In those instances, the rollback section should be filled with the steps to rollback. If the rollback is easy to do, just write that rollbacking is safe, no steps.
- Use the user instructions to enrich the context (if present).
- DO NOT change code from the commits. Your ONLY job is to write the PR, not to change the code. If you think some code should ABSOLUTELY be changed, stop the PR process and ask the user to make the change, but NEVER change it yourself.
- DO NOT add AI attribution in the PR body.
- DO NOT use bullets in the PR body. Instead, write terse paragraphs (and code blocks/diagrams in "Qué hay de nuevo?").
- Always match the writing style of the user.
- In Spanish, use "la PR", not "el PR".
- Backticks and code blocks get mangled by the shell, so write the body to a file under `/tmp/opencode` and pass it with `--body-file` instead of `--body`.
