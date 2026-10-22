# Eval: "cut the epic into stories"

Done scenario for story-spec. Run by hand or with `claude -p` in a project checkout.

## Setup

Epic 18 (chat) in a mobile project: 4 large parts, two of them with sub-parts. The coordinator assigned the
range `D-1800...D-1819`. The profile has `stack: mobile`.

## Prompt

> Cut epic 18 into stories and write the specs of the first two.

## Expected (all points)

1. The agent picks `story-spec`; before numbering it looks at open PRs and branches.
2. The story list: each story at most 300 lines / 5 code files, each with files, complexity and a done command.
3. Keys are only `18-N` and `18-Na`: `grep -nE '^\s+[0-9]+-[0-9]+[a-z][0-9]' sprint-status.yaml` prints nothing
   (a sub-part of a sub-part is renumbered with letters, not `18-1b1`).
4. `sprint-status.yaml` has `epic-18-retrospective: required`.
5. Each spec: `**Status:**` equals the YAML `status:`, `**Complexity:**` with a reason, `**Dev model:**` as a
   literal (`opus` for high, `sonnet` for normal - not "heavy/default"), `**Size:**`, `**Modules:**`,
   **`**Analytics:**`** (mobile), the five sections, `## Done command`.
6. Decision numbers only from `D-1800...D-1819`, with the line `numbers from D-1800, epics.md at <sha>`.
7. Specs do not become `ready-for-dev` without two roundtable passes.

## Failure

- `**Dev model:** default` (a role instead of a literal), a key like `18-1b1`, a "full screen + API" story without
  a split, no `Analytics` line, a number outside the range.
