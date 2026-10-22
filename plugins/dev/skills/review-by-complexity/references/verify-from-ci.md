# Verifying through CI

**Verification is part of the work, not a report about it:** push and read what CI did with that commit - the verdict,
and on red, the log. Write the real outcome and the sha it belongs to.

## What the session does, what CI does

| Session (before the push) | CI (after the push) |
|---|---|
| tests the change touches; typecheck / quality check / project guards | the full test suite |
| a "like CI" run (`ci:local` or similar) if tests call git or spawn processes | all jobs required for the PR |

A "verified" line always names the commit. A claim about a system you cannot reach from the branch is written as a
question with the person who can check it, not as an answer.

## Reading a red run

```sh
# R = repo API root (Gitea: $GITEA_URL/api/v1/repos/$FORGE_OWNER/<repo>; GitHub: https://api.github.com/repos/$FORGE_OWNER/<repo>)
run=$(curl -sfn "$R/actions/runs?head_sha=<sha>" | jq -r '.workflow_runs[0].id')
curl -sfn "$R/actions/runs/$run/jobs" | jq -r '.jobs[] | "\(.id) \(.name) \(.conclusion)"'
curl -sfn "$R/actions/jobs/<job-id>/logs" | grep -nE 'FAIL|Error|error:|exit code' | head -40
```

On GitHub replace `-n` with `-H "Authorization: Bearer $GH_TOKEN"` and add `-L` for the log download.
If the log does not settle it, reproduce locally the way CI runs, or rerun (below). Do not guess.

## Decision: rerun, merge the default branch in, or fix

| Sign in the log | What it is | What to do |
|---|---|---|
| "N passed, N total" but the shard FAILs; job ended 137 / SIGKILL | killed worker, runner memory | `rerun-failed-jobs` |
| `ECONNRESET`, DNS, "Could not resolve host" in `npm ci` / `docker build` / checkout | runner network | `rerun-failed-jobs` |
| 3 or more unrelated page tests failed with a time near `testTimeout` | runner under load | `rerun-failed-jobs` |
| A test already fixed on the default branch (fix merged after the branch was cut) | stale branch | **merge `origin/<default_branch>`** into the branch (merge, not rebase of a published branch) - rerun will not help |
| Failure depends on time of day, disk speed, order (`--randomize`) | a deterministic dependency in the test | merge the fix from the default branch if it exists; otherwise a fix story, not endless reruns |
| A test the PR's diff touches fails | the PR's code | fix in the PR branch |

Rules:
- **Rerun only when the PR has no pending dev-loop gate:** otherwise a rerun burns a loop attempt.
- One rerun per suspicion. A second red **from the PR's own code** - stop and report to the dispatcher (the
  coordinating agent session): a fix in the branch or a redo from the same spec (for `normal`, possibly with the
  heavy model) is the dispatcher's decision, not the reviewer's.
- Green after a rerun is "a flake, cause unknown" with run numbers; a repeating flake is a candidate for a fix story.
- After merging the default branch in, CI runs again on the new sha; the review verdict belongs to that sha only.

```sh
curl -sn -X POST "$R/actions/runs/$run/rerun-failed-jobs" -o /dev/null -w '%{http_code}\n'   # 201 on Gitea; GitHub: gh run rerun --failed
git -C <worktree> fetch origin && git -C <worktree> merge --no-edit origin/<default_branch> && git -C <worktree> push
```

## The exact head

- Take status for the PR's `head.sha` (`GET /pulls/<N>`), not for the branch by name.
- A new push after review is a new sha: status and review verdict are re-checked.
- The merge carries this sha as the expected head: the forge refuses if the branch moved.
