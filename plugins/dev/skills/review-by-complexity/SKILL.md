---
name: review-by-complexity
description: >
  Reviews a story PR according to its complexity: normal - one round of two layers, high - up to three rounds; checks
  green CI on the exact head, decides rerun of a flake versus merging the default branch in, and never merges
  without explicit permission. Use when reviewing a story PR, triaging red CI, or deciding if a PR is ready to merge.
license: MIT
compatibility: "Claude Code >= 2.1, Codex; optional BMAD bmad-code-review; curl, jq; Gitea (token via ~/.netrc) or GitHub (GH_TOKEN) API access."
metadata:
  category: development
  owner: maintainer
  maturity: trial
  added: "2026-10-22"
  updated: "2026-10-22"
  projects: all
  cluster: review
  leader: "true"
  decided-by: "maintainer, 2026-10"
  review-by: "2027-01-22"
---

# Review by complexity and the CI verdict

## Environment check

- The PR number and its spec (the `**Complexity:**` line). No line - decide from the spec: migration/schema,
  money, lock races, a published contract -> `high`, otherwise `normal`.
- Forge credentials work: read `head.sha` of the PR (`GET <R>/pulls/<N>`, see the `feature-branch-flow` skill's
  forge-API reference for both Gitea and GitHub).
- A worktree on the PR head (not the main checkout) for reading code and targeted test runs.
- Fallback: API unavailable - review the diff only, state "CI not verified", and never declare the PR ready to merge.
  No `bmad-code-review` - run the layers below by hand from a checklist.

## When to use

- Reviewing the PR of a story, fix or document.
- CI of the PR is red: decide whether it is the code, a runner flake, or something already fixed on the default branch.
- Deciding whether a PR is ready to merge and compiling the list for whoever merges.

## Rules

1. **Rounds follow complexity, not size:**
   - `normal` - **one round, two layers:** Blind Hunter (the diff without context) and Acceptance Auditor (against the spec's AC);
   - `high` - **up to three rounds:** round 1 - Blind Hunter, Edge Case Hunter, Acceptance Auditor; each later
     round runs only the layer whose class of findings appeared in the previous one.
2. All layers use the default ("working") model. A local-model note (PR comment `<!-- local-model-pass -->`) holds
   **questions** to check against the tree, not findings; no comment is not an error.
3. **`patch` findings are applied without asking;** a finding is closed only when `git diff` shows the fix.
4. A round whose findings are all wording (prose, comments, records) earns at most one more; leftover prose goes to the ledger.
5. **The last round means the PR is done.** Anything unresolved becomes a ledger entry (`review.ledger`): what, how measured, whose.
6. **Two exceptions block the merge** regardless of round count: a finding that changes behavior visible to a caller,
   and a finding that makes a published contract lie. Still open - stop and say so.
7. **A runtime-code fix in a round buys one pass over that fix only** (`followup_review_recommended: true`, with the
   commit). An unreviewed fix is not a fix; a round with no changes is not earned.
8. A guard added in a round gets its own mutant in the same round.
9. **Verification is the CI verdict on the exact head**, not the story's self-report and not a full test run in the
   session. A review reruns only the tests a finding is about. How to read CI:
   [references/verify-from-ci.md](references/verify-from-ci.md).
10. **A red CI is read from the job log**, never guessed. Runner flake -> `rerun-failed-jobs`; fixed on the default
    branch -> merge `origin/<default_branch>` into the branch; a second red from the PR's own code -> stop and report;
    whether to redo the story from the same spec (and with the heavy model) is the dispatcher's call (the
    coordinating agent session), not the reviewer's. A green rerun is called "a flake of unknown cause", not "CI is green".

## Reviewer must not

- **Merge a PR without explicit permission.** Review is not merge. Only the permitted party merges: the dispatcher
  under the repo's standing permission (green CI on the exact head + converged review + queue paused) or a human
  naming the PR number. A generic "go ahead" or "fix it" is not permission to merge.
- Push to the default branch or `main`, rewrite the branch's history, or close someone else's PRs.
- Declare "ready" without green CI on the **same** sha that was reviewed; after new pushes, check again.
- Run the full test suite instead of CI, or repeat numbers from the story's report as verified.
- Open a round beyond the limit silently.

## How to apply

```sh
# R = repo API root (see the forge-API reference of feature-branch-flow); Gitea shown, GitHub uses the same paths with a Bearer header
sha=$(curl -sfn "$R/pulls/<N>" | jq -r .head.sha)
curl -sfn "$R/commits/$sha/status" | jq -r '.state, (.statuses[] | "\(.context): \(.status)")'
# diff and spec -> layers by complexity -> patch fixes pushed to the PR branch -> new sha -> check status again
```

The review result is a PR comment:

```
Review <normal|high>, round <k>/<limit>, head <sha7>: CI <success|failure: job, cause>.
Findings: patch <n> applied (<commit>), defer <n> -> ledger, decision-needed <n>.
Exceptions (behavior/contract): none | <what>. Ready to merge: yes/no - <why>. I do not merge.
```

## Verification

- The PR has a summary comment with the head sha; the combined status for that sha is `success`.
- Every `patch` finding is visible in `git diff`; every deferred one is a ledger line with an owner.
- The PR was not merged by the reviewer (`merged=false` unless permission was given).

## Exceptions and human stop

- `decision-needed`: the fix is ambiguous and changes a published contract (error code, permission, an operation's
  promise) - stop and ask the owner; do not decide ad hoc. In an unattended run take the smaller risk and record the
  decision plus the rejected alternative in the ledger.
- Data-deleting migrations, production, money, permissions - the merge waits for the owner whatever the review verdict.
- A red CI that cannot be read or reproduced - stop with a description; no blind rerun.

## Project profile

`docs/ai/project-profile.yaml`: `repo`, `ci.pr_check` (the check required on the head), `ci.epic`,
`review.ledger` (path of the deferred-work file), `merge_style` (only to name the style in the list for whoever merges).
