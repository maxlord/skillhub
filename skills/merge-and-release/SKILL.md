---
name: merge-and-release
description: >
  Merges PRs in the repo's style and ships a release: who merges and when, release branch (release/vX or the default branch)
  -> PR into main as a merge commit, tag by workflow, main -> default-branch sync, deploy only on the owner's word.
  Use when merging a PR, preparing a release, tagging, syncing main, or deploying to production.
license: MIT
compatibility: "Claude Code >= 2.1, Codex; git >= 2.30, curl, jq; Gitea or GitHub Actions (release and deploy workflows); API token via ~/.netrc (Gitea) or GH_TOKEN (GitHub)."
metadata:
  category: release
  owner: maintainer
  maturity: trial
  added: "2026-10-22"
  updated: "2026-10-22"
  projects: all
  cluster: release
  leader: "true"
  decided-by: "maintainer, 2026-10"
  review-by: "2027-01-22"
---

# Merge and release

## Environment check

- Forge credentials (`~/.netrc` for Gitea, `GH_TOKEN` for GitHub), `jq`, and a worktree for the release branch
  (do not touch the main checkout while a queue runs).
- `docs/ai/project-profile.yaml`: `merge_style`, `release.workflow`, `release.deploy`, `release.version_files`,
  `release.tag` (`workflow` - the release workflow tags; `push` - a human or the dispatcher pushes the tag on the
  merge commit), `release.branch` (`release/vX` - a dedicated branch; `dev` - a PR straight from the default branch to `main`).
- The project's release scripts if any (`release.scripts`): `prepare` and `sync`.
- Fallback: no profile - do not guess the merge style or tagging mode, ask the owner. No scripts - do the steps
  below by hand. No rights to dispatch a workflow or push a tag - prepare everything and stop for a human.

## When to use

- Merging a PR into the default branch (your own merge list, while the queue is paused).
- Shipping a release: branch, PR into `main`, tag, release, sync, deploy.
- Rolling back a release or shipping a hotfix.

## Rules: who merges and how

1. **A story agent and a reviewer do not merge.** The dispatcher (the coordinating agent session) merges under the
   repo's standing permission when all three hold: green CI on the **exact head**, review converged, queue paused
   between stories. Other PRs merge only by a number the owner named. A generic "go ahead / fix it" is not
   permission for new merges.
2. **Always wait for the owner:** migrations that delete data, production, money, permissions, a release into `main`
   without their word.
3. **Style comes from the profile, not habit:** `merge_style.story` (`merge` or `squash`, per repo),
   `merge_style.loop` = `fast-forward-only` for dev-loop landings, `merge_style.release` = **merge commit**.
4. Every merge carries the verified `head` sha and deletes the branch; wait by PR number.
5. Merge in queue pauses, as a batch from a list: number - style - CI - review. A guard refusal is not bypassed:
   hand the list to the owner.

## Rules: release

6. **The release branch follows `release.branch`.** `release/vX`: branch `release/vX.Y.Z` from a fresh
   `origin/<default_branch>` holding only the version bump in every `release.version_files` plus the changelog.
   `dev`: bump by an ordinary PR, then a PR default branch -> `main`. If the key is missing, look at how the last
   release went (`git log --merges origin/main -3`) and ask the owner.
7. **The release PR into `main` merges as a merge commit, never squash.** Squash diverges `main` and the default
   branch with identical trees: the next release PR then shows false conflicts.
8. **Never tag by hand when a workflow exists.** `release.tag: workflow` - dispatch `release.workflow` from `main`
   with the version; it refuses if the version does not match the files or the tag exists. `release.tag: push` - an
   annotated tag on the **named** merge commit of `main` (`git tag -a vX.Y.Z -m vX.Y.Z <sha>`), not on `HEAD`.
   A published tag is never moved.
9. **Right after a release, a sync PR `main` -> default branch** as a merge commit. Without it the default branch
   does not know the release merge commit.
10. **Deploy = `release.deploy` on the tag; production only on the owner's word**, every time anew. Respect
    `release.deploy_window` if set. On production deploy the image pinned by digest from the release; never run
    `compose up` on production without an explicitly pinned image (`<SERVICE>_IMAGE=...@sha256:...`), or a stale
    local build gets picked up.
11. A `workflow_dispatch` workflow works only when its file is already on `main`: a workflow edit takes effect after the release.
12. Rollback: a revert commit and a new release, or deploy the previous tag. Hotfix: `hotfix/vX.Y.Z` from `main`,
    PR into `main`, then the same sync PR.

## How to apply

```sh
# Merge a PR (if allowed): one command, one merge, absolute script path
bash /abs/path/to/forge-pr.sh <repo> merge <N> <merge_style.story>
# --- Release (queue paused) ---
scripts/release/prepare.sh vX.Y.Z --push       # or by hand: branch from origin/<default_branch>, bump, changelog, push
# PR release branch -> main, CI green, review -> merge as a merge commit
bash /abs/path/to/forge-pr.sh <repo> merge <N> merge
git -C "$WT" fetch origin && git -C "$WT" log -1 --format='%H %s' origin/main   # the release merge commit
# Tag via workflow (URL as the first curl argument so allow-rules match). Gitea:
curl "$GITEA_URL/api/v1/repos/$FORGE_OWNER/<repo>/actions/workflows/release.yml/dispatches" -sS -X POST -n \
  -H 'Content-Type: application/json' -d '{"ref":"main","inputs":{"version":"vX.Y.Z"}}'
# GitHub equivalent:
gh workflow run release.yml --repo "$FORGE_OWNER/<repo>" --ref main -f version=vX.Y.Z
# Sync main -> default branch at once
scripts/release/sync-main-to-dev.sh            # PR main -> default branch, merge commit
# Deploy - only after the owner's word in this session (same call shape, workflow deploy.yml, input tag=vX.Y.Z)
gh workflow run deploy.yml --repo "$FORGE_OWNER/<repo>" --ref main -f tag=vX.Y.Z
```

`forge-pr.sh` comes from the `feature-branch-flow` skill or the project's copy; call it by absolute path. The
dispatch endpoints for both forges are in that skill's forge-API reference.

## Verification

- `GET /pulls/<N>` -> `merged=true`; the release PR into `main` has two parents (`git log -1 --format=%P origin/main`).
- The tag points to the `main` merge commit: `git rev-list -n1 vX.Y.Z` equals the sha from the merge step; a release object exists on the forge.
- The sync PR is merged: `git merge-base --is-ancestor origin/main origin/<default_branch>` exits 0.
- After deploy, the version and commit from the service's health endpoint match the tag.

## Exceptions and human stop

- Production deploy, a release into `main`, data-deleting migrations, money, permissions - only on the owner's word.
- A tag push rejected by a proxy (403) - the owner pushes the tag; name the sha in the message.
- The release PR conflicts with `main` - the previous sync was not merged or was squashed: stop, investigate, do not rewrite history.

## Project profile

`docs/ai/project-profile.yaml`: `repo`, `forge`, `default_branch`, `merge_style.{story,loop,release}`, `release.workflow`,
`release.deploy`, `release.version_files`, `release.tag` (`workflow` | `push`), `release.branch` (`release/vX` | `dev`),
`release.deploy_window`, `release.scripts`, `ci.pr_check`.
