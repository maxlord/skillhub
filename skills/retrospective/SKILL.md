---
name: retrospective
description: >
  Closes an epic with a retrospective: an agent in a worktree reviews what the epic shipped and where it failed,
  checks docs and diagrams, opens a documents-only PR, and fixes findings at once in separate PRs. Use when an
  epic's last story is merged, an epic is deferred with a tail, or a retrospective line is needed.
license: MIT
compatibility: Any coding agent (Claude Code, Codex); optionally the BMAD bmad-retrospective skill; git; npx with @mermaid-js/mermaid-cli (mmdc) for diagram checks.
metadata:
  category: process
  owner: maintainer
  maturity: trial
  added: "2026-10-22"
  updated: "2026-10-22"
  projects: all
  cluster: retrospective
  leader: "true"
  decided-by: "maintainer, 2026-10"
  review-by: "2027-01-22"
---

# A retrospective closes the epic

## Environment check

- The project checkout is on a fresh `origin/<default_branch>`; the retro runs in a separate worktree and the main
  checkout is left alone.
- Available: the epic's sprint status file, the story specs, the review ledger, and the epic's PR numbers.
- For diagrams: `npx` (mermaid-cli); in a sandbox run `mmdc` with `-p` and a config `{"args":["--no-sandbox"]}`.
- Fallback: no `bmad-retrospective` - write the retro sections below by hand; no `npx` - check Mermaid blocks by
  eye and note "mmdc not run" in the PR; no forge API access - take the PR list from
  `git log --merges origin/<default_branch>`.

## When to use

- The last story of an epic is merged: run the retro before the next epic is planned or queued.
- The owner deferred the tail of an epic: run the retro on what passed.
- A new epic: its `epic-N-retrospective: required` line is created together with it.

## Rules

1. **A retrospective closes every epic.** Every unfinished epic in the sprint status file has a line
   `epic-N-retrospective: required` (not `optional`; no separate `final` lines, an interim retro is a comment).
2. **The retro is run by an agent on the default model in a worktree**; the queue does not wait for it.
   The retro of a closed epic is queued before the first story of the next one.
3. **The result is a documents-only PR** (retro, ledger, module contexts, architecture, README, sprint status).
   No code changes in the retro PR.
4. **Documentation checklist** (one line in every retro): the architecture overview (or the project's system map)
   and `README.md` match what the epic shipped. Diagrams are Mermaid only (`flowchart`, `sequenceDiagram`,
   `erDiagram`), no images; anything unverified is a dashed `[[clarify]]`. Every block goes through `mmdc`.
5. If the epic changes the system's composition (a new service, store, external service, host, or a flow between
   repos), the shared system map is updated too.
6. **Module contexts** (`docs/context/<module>.md`) are updated for what the epic changed in Provides.
7. **Findings are fixed at once:** agent items (plugin, CI, docs, a rule) go right after the retro PR to a separate
   agent as **separate PRs**; they do not pile up. Items for the owner go to the owner as one list.
8. **Hub line:** "which practices from the epic should be moved into the skills hub or corrected there" becomes a
   `candidate` issue in the skills hub repo; a skill that helped or got in the way gets a thumbs-up/down with the
   skill's name. A project skill past its `review-by` date becomes a line "review X".
9. CI flakes found during the epic go into the retro with run numbers and a decision: a fix story or keep watching.

## How to apply

```sh
git -C "$CHECKOUT" fetch origin
git -C "$CHECKOUT" worktree add "$WT_ROOT/<repo>-retro-<N>" -b docs/epic-<N>-retro origin/<default_branch>
# 1. Facts: epic PRs, ledger, queue stops, red CI, review rounds, tokens/time if available
# 2. bmad-retrospective (or the sections below) -> <retro.dir>/epic-<N>-retro-<date>.md
# 3. Documentation checklist; run mmdc on every changed .md that has Mermaid:
npx -y @mermaid-js/mermaid-cli -i docs/architecture/overview.md -o "$TMPDIR/mmdc-out.md"
# 4. sprint status: epic-<N>-retrospective: done; open the documents PR into the default branch
# 5. Agent items -> separate agents and PRs; owner items -> a list; candidates -> issues in the skills hub repo
```

Retro file sections: what shipped (PRs, versions) · what worked · what failed (stops, flakes, review rounds,
complexity underestimates) · documentation checklist · actions (who, PR/issue) · items for the owner · skills hub.

## Verification

- The epic's `sprint-status.yaml` has `epic-<N>-retrospective: done`; later epics have `required`.
- The retro PR contains documents only (`git diff --stat origin/<default_branch>` shows no code).
- `mmdc` passed on every changed file with Mermaid (output in the PR description).
- Every agent item has a separate PR or issue number; owner items are a list in the report.

## Exceptions and human stop

- A retro item that changes production, money, permissions or a published contract goes only on the owner's list.
- If the retro finds the epic shipped something other than the specs say (drift), describe it and propose a
  correct-course step to the owner instead of fixing it in the retro PR.

## Project profile

`docs/ai/project-profile.yaml`: `retro.dir` (where the retro file goes), `sprint_status` (path), `review.ledger`,
`docs.architecture` (overview and system map).
