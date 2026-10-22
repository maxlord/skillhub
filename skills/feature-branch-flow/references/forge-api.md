# Forge API cheat sheet (Gitea and GitHub)

Pick the column by `forge:` in the project profile. `<R>` is the repo root:
- Gitea: `$GITEA_URL/api/v1/repos/$FORGE_OWNER/<repo>`; auth only via `~/.netrc` (`curl -n`).
- GitHub: `https://api.github.com/repos/$FORGE_OWNER/<repo>`; header `Authorization: Bearer $GH_TOKEN`
  (env var, never a literal token). `gh api repos/...` is an equivalent.

Never put a token on the command line or in a file under version control.

## Pull requests

| Action | Gitea | GitHub |
|---|---|---|
| Open | `POST <R>/pulls` `{head, base, title, body}` | same endpoint; `gh pr create --head --base --title --body-file` |
| State | `GET <R>/pulls/<N>` → `state`, `merged`, `mergeable`, `head.sha`, `base.ref` | same fields |
| Status of the exact head | `GET <R>/commits/<sha>/status` → combined `state`, `statuses[].context/status` | same path (combined status) plus `GET <R>/commits/<sha>/check-runs` for Actions checks |
| Merge | `POST <R>/pulls/<N>/merge` `{Do, head_commit_id, delete_branch_after_merge: true}` | `PUT <R>/pulls/<N>/merge` `{merge_method, sha}`; then `DELETE <R>/git/refs/heads/<branch>` (or enable "auto-delete head branches" in repo settings) |
| Close | `PATCH <R>/pulls/<N>` `{state: "closed"}` + `DELETE <R>/branches/<branch>` | `PATCH <R>/pulls/<N>` `{state: "closed"}` + `DELETE <R>/git/refs/heads/<branch>` |
| Comment | `POST <R>/issues/<N>/comments` `{body}` | same |
| Open PRs | `GET <R>/pulls?state=open&limit=50` | `GET <R>/pulls?state=open&per_page=50` |

Merge styles: Gitea `Do` = `merge`, `squash`, `rebase`, `fast-forward-only`; GitHub `merge_method` = `merge`,
`squash`, `rebase` (no fast-forward-only: land such branches by pushing the tip to the base with a protected-branch
bypass the owner configured, or use `rebase`). Without the exact head sha the forge merges whatever the branch holds
at request time, not what passed CI. Always send it.

**Gitea quirk after merge:** once the branch is deleted, `head.ref` is rewritten to `refs/pull/<N>/head`.
Wait for a merge by PR number, never by branch name:

```sh
until curl -sfn "<R>/pulls/<N>" | jq -e .merged >/dev/null; do sleep 30; done   # run in the background
```

## CI

| Action | Gitea Actions | GitHub Actions |
|---|---|---|
| Runs of a commit | `GET <R>/actions/runs?head_sha=<sha>` | `GET <R>/actions/runs?head_sha=<sha>` |
| Jobs of a run | `GET <R>/actions/runs/<run>/jobs` → `id`, `name`, `conclusion` | same |
| Job log | `GET <R>/actions/jobs/<job-id>/logs` | same (302 to a download URL; use `curl -L`); `gh run view --log-failed` |
| Rerun failed jobs | `POST <R>/actions/runs/<run>/rerun-failed-jobs` | same endpoint; `gh run rerun --failed` |
| Workflow dispatch | `POST <R>/actions/workflows/<file>/dispatches` `{ref, inputs}` | same endpoint; `gh workflow run <file> --ref main -f k=v` |

- Read a red run from the **job log**; take the job id from `runs/<run>/jobs`, not from a task id.
- A `workflow_dispatch` workflow works only when its file already exists on `ref` (usually `main`).

## Guard rules (agent permission systems)

A command allow-list matches the command text literally:
- call the script by its **absolute path** (`bash /abs/path/forge-pr.sh <repo> merge <N> <style>`), no `cd`, `&&` or loops;
- one merge = one command; a batch is several separate calls;
- a refusal on a merge is not worked around another way: hand the owner a list of PR numbers.

## Branches

- The merge deletes the remote branch (flag above). Locally run `git remote prune origin`.
- Never delete someone else's branch. Delete your abandoned one only after `git rev-list --count origin/<default_branch>..<branch>`
  (non-zero is expected only for an abandoned draft) and with its diff in the report.
- The repo-level "delete branch after merge" setting applies only to web-UI merges on Gitea; API merges need the request flag.
