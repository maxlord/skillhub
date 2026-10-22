# Eval: "start story 3-2"

Run by hand or with `claude -p` in a checkout of the project.

## Setup

Checkout on the default branch, clean. `docs/ai/project-profile.yaml` has `merge_style`
(`story: merge`, `loop: fast-forward-only`, `release: merge`) and `forge`. The forge token is configured
(`~/.netrc` for Gitea or `GH_TOKEN` for GitHub).

## Prompt

> Start story 3-2 (the spec is ready), then open a PR.

## Expected (all points)

1. The agent uses the `feature-branch-flow` skill (via `Skill` or by reading `SKILL.md`).
2. Environment check: `origin` matches the profile's forge, auth works, profile read.
3. `git fetch origin`, then `git worktree add <absolute path outside the checkout> -b feat/3-2-<slug> origin/<default_branch>`;
   the main checkout stays on the default branch (`git status -sb` identical before and after).
4. Commits and push come from the worktree; the PR is opened right after the first push
   (`forge-pr.sh ... open`) and its number is recorded.
5. The PR description has the story key 3-2 and the output of the done command.
6. The story agent does **not** merge the PR and does not push to the default branch; the report ends with the PR number and CI state.

## Fail

- The branch was created by switching the main checkout (`git checkout -b` there) or from an unmerged branch without a note.
- The branch name has no story key, or a key with a digit after the letter.
- A merge, or a push to the default branch, was performed.
