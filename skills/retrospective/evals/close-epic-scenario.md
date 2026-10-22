# Eval: "close epic 3 with a retrospective"

Done scenario for retrospective. Run by hand or with `claude -p` in a project checkout.

## Setup

The last story of epic 3 is merged. The epic added a new service (a flow between repos), the ledger has two
entries, and there was one CI flake during the epic (a rerun was green). `sprint-status.yaml` has
`epic-3-retrospective: required`; epic 4 has no retrospective line.

## Prompt

> Epic 3 is closed, run the retrospective.

## Expected (all points)

1. The agent picks `retrospective`; works in a worktree off `origin/<default_branch>`, branch `docs/epic-3-retro`.
2. The retrospective file has the sections: what shipped, what worked, what failed (the flake with run numbers),
   documentation checklist, actions, items for the owner, the skills-hub line.
3. The architecture overview, the README **and the system map** are updated (the epic added a service); diagrams
   are Mermaid and `mmdc` was run.
4. `epic-3-retrospective: done`; epic 4 gets `epic-4-retrospective: required`.
5. The retro PR contains documents only; agent action items are separate PRs/agents with numbers in the report;
   a practice candidate is a `candidate` issue in the skills hub repo.

## Failure

- Code edited in the retro PR, "later" remarks without a PR/issue, a picture instead of Mermaid, a
  retrospective without the documentation checklist.
