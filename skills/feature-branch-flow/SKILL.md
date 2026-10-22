---
name: feature-branch-flow
description: >
  Guides the git flow for a story: a branch from a fresh default branch in its own worktree, a PR right after the
  first push, merge in the style from the project profile, branch deletion, fast-forward-only landings for an
  unattended dev loop. Use when starting a story, opening or merging a PR, or cleaning up branches.
license: MIT
compatibility: "Claude Code >= 2.1, Codex; git >= 2.30, curl, jq; Gitea (token via ~/.netrc) or GitHub (GH_TOKEN) API access."
metadata:
  category: development
  owner: maintainer
  maturity: trial
  added: "2026-10-22"
  updated: "2026-10-22"
  projects: all
  cluster: git-flow
  leader: "true"
  decided-by: "maintainer, 2026-10"
  review-by: "2027-01-22"
---

# Branch -> PR -> merge -> delete the branch

## Environment check

- `git remote get-url origin` matches `forge` in the profile (Gitea or GitHub).
- Auth works: Gitea `curl -sfn "$GITEA_URL/api/v1/user" | jq -r .login`; GitHub
  `curl -sf -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/user | jq -r .login`.
- `jq` is installed and `docs/ai/project-profile.yaml` exists (keys: see "Project profile").
- Fallback: no profile - assume `default_branch` from `git symbolic-ref refs/remotes/origin/HEAD`, never guess the
  merge style, ask the repo owner. No credentials or no push rights - prepare the branch and commits locally and
  stop for a human (never ask for a token in chat). `origin` points to the wrong forge - fix it before any push.

## When to use

- Starting a story, fix or document - any change that will land in the repo.
- Opening, merging (if you are allowed, see "Exceptions") or closing a PR; cleaning up branches.
- Landing a branch built by an unattended dev loop (e.g. a BMAD-based loop) or a sweep (commits in the local default branch).

## Rules

1. **Everything through the forge API.** Remote, PR, statuses, CI logs and reruns go through the forge API or the
   forge CLI. Examples for Gitea and GitHub: [references/forge-api.md](references/forge-api.md).
2. **One story = one branch from a fresh `origin/<default_branch>`**, fetched right before starting. Not from
   another unmerged story's branch, not reused. If you must branch from an unmerged one, say so on the first
   line of the PR description ("merge after #N").
3. **Branch name:** `<type>/<key>-<slug>`: `feat/`, `fix/`, `docs/`, `ci/`, `chore/`; story key `N-N[a-z]`.
4. **Do not switch the main checkout.** It stays on the default branch: the dev loop lands stories there with
   `--ff-only`, and a foreign branch causes "Diverging branches". Do your work in a `git worktree` at an
   **absolute** path outside the main checkout; remove it after the PR.
5. **No direct pushes to the default branch or `main`.** "Push it" means "branch + PR". `main` changes only via a release PR.
6. **Open the PR right after the first push**, before review; review fixes are further pushes to the same branch.
   The description has the story key, what was done, the done-command output, deviations, and the agent's signature.
7. **The PR number is the only key.** On Gitea, `head.ref` is rewritten to `refs/pull/<N>/head` after a merge: wait
   for a merge via `GET /pulls/<N>` -> `merged == true`, and read CI by commit sha, never by branch name.
8. **Merge only by the repo's rules and only if you are allowed** (see "Exceptions"): green CI on the exact head,
   review converged, queue paused. Style from the profile: `merge_style.story` for ordinary PRs,
   `merge_style.loop` (usually `fast-forward-only`) for dev-loop landings, `merge_style.release` for a release PR
   (merge commit, not squash).
9. **Always pass the verified head sha** (`head_commit_id` on Gitea, `sha` on GitHub) and delete the branch on merge:
   exactly what passed CI is merged. A PR closed without merging also loses its own branch.
10. **Dev-loop landing is fast-forward-only:** after a run or sweep the local default branch goes up as a branch
    (`git push origin <default_branch>:refs/heads/<branch>` from a worktree), then a PR, then a `fast-forward-only`
    merge onto the same commit - so local and remote default branches converge. Where the forge lacks that style
    (GitHub), push the verified tip to the base by hand under the owner's branch protection rules.
11. **Anything dangerous needs a human stop:** rewriting shared history, force-pushing, deleting someone else's
    branches. Bulk deletion: write the list to a file first, then wait for the owner's word.
12. **One command, one action.** A merge is one script call at an absolute path, with no `cd`, `&&` or loops:
    the agent guard's allow-rules match only that form.

## How to apply

```sh
# 0. Profile
cat docs/ai/project-profile.yaml        # repo, forge, default_branch, merge_style, ci.pr_check
# 1. Branch from a fresh default branch in a separate worktree (absolute path outside the checkout)
git -C "$CHECKOUT" fetch origin
git -C "$CHECKOUT" worktree add "$WT_ROOT/<repo>-<key>" -b feat/<key>-<slug> origin/<default_branch>
# 2. Work, commit, push the branch
git -C "$WT_ROOT/<repo>-<key>" push -u origin feat/<key>-<slug>
# 3. Open the PR at once (body = file with description and done-command output)
bash "$SKILL_DIR/scripts/forge-pr.sh" <repo> open feat/<key>-<slug> <default_branch> "feat: <key> <summary>" /path/to/body.md
# 4. Before merging: CI on the exact head
bash "$SKILL_DIR/scripts/forge-pr.sh" <repo> status <N>
# 5. Merge (if allowed): style from the profile, branch deleted
bash "$SKILL_DIR/scripts/forge-pr.sh" <repo> merge <N> <merge_style.story>
# 6. Cleanup
git -C "$CHECKOUT" worktree remove "$WT_ROOT/<repo>-<key>"; git -C "$CHECKOUT" remote prune origin
```

`$SKILL_DIR` is this skill's directory (`${CLAUDE_SKILL_DIR}` in Claude Code), `$CHECKOUT` the main checkout,
`$WT_ROOT` the worktree directory. The script reads `FORGE` (`gitea`|`github`), `FORGE_OWNER`, and `GITEA_URL`
(Gitea) or `GH_TOKEN` (GitHub); `PR_SIGNATURE` optionally appends an agent signature to comments.

## Verification

- `git -C "$CHECKOUT" status -sb` - main checkout on the default branch, clean.
- `forge-pr.sh <repo> status <N>`: `base=<default_branch>`, `ci=success` on the same `head` as in the PR description.
- After the merge: `merged=true`, and `git ls-remote --heads origin <branch>` is empty.

## Exceptions and human stop

- **A story agent does not merge its PR.** The dispatcher (the coordinating agent session) merges under the repo's
  standing permission (green CI on the exact head + converged review + queue paused), or a human does. Any other PR
  merges only by a number the owner named.
- **Always wait for the owner:** production, money, permissions, migrations that delete data, a release into `main`
  without their word.
- If a guard or classifier refuses a merge, do not work around it: compile a list "number - style - CI - review"
  and hand it to the owner.
- A conflict with the default branch in files that are not yours, a failure in someone else's part of CI, a branch
  with unknown commits - stop and describe.

## Project profile

`docs/ai/project-profile.yaml`: `repo`, `forge`, `default_branch`, `merge_style.story`, `merge_style.loop`,
`merge_style.release`, `ci.pr_check` (the check to wait for on the head).
