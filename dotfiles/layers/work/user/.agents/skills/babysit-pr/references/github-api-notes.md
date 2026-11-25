# GitHub CLI and API Notes

## PR and checks

```bash
gh pr view <pr> -R <owner/repo> \
  --json number,url,state,isDraft,headRefName,headRefOid,statusCheckRollup,reviews,comments,commits
```

The watcher reads `statusCheckRollup`, normalizes workflow and job names, and selects the latest run per normalized name. It ignores `hermes/approval-gate` and `bors`, and inspects `comments` and `commits` to detect recently posted `fin review` trigger comments while waiting for the check run to start.

The AI reviewer check appears either as CheckRun `fin review` (normalized to `fin-review`) or, on legacy Hermes setups, workflow `Hermes` and job `pr-pipeline / code-review` (normalized to `hermes/pr-pipeline/code-review`). Note that `fin review` may complete with `conclusion: "SUCCESS"` even when it leaves inline findings without an `LGTM`.

## Trigger review

```bash
gh pr comment <pr> -R <owner/repo> --body 'fin review'
```

Draft PRs require this after every push. Ready-for-review PRs trigger the reviewer automatically on push.

## Fetch inline comments

```bash
gh api 'repos/<owner>/<repo>/pulls/<pr>/comments?per_page=100' --paginate
```

The bot appears as `fin-review[bot]` in REST and `fin-review` in GraphQL/`gh pr view`.

## Reply to a finding

```bash
gh api repos/<owner>/<repo>/pulls/<pr>/comments/<comment-id>/replies \
  -f body='[babysit] fixed in <commit>'
```

For a declined finding, use `[babysit] <justification>` instead.

## Find and resolve its thread

Fetch thread IDs and comment database IDs:

```bash
gh api graphql \
  -f query='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:100){nodes{id isResolved comments(first:100){nodes{databaseId author{login} body}}}}}}}' \
  -F owner=<owner> -F repo=<repo> -F number=<pr>
```

Resolve only a `fin-review` thread whose finding was fixed and pushed:

```bash
gh api graphql \
  -f query='mutation($thread:ID!){resolveReviewThread(input:{threadId:$thread}){thread{id isResolved}}}' \
  -f thread=<thread-id>
```

## Mark ready

```bash
gh pr ready <pr> -R <owner/repo>
```

Do this only after the current SHA has `fin-review` LGTM and every non-ignored check passes.
