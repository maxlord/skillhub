---
name: story-spec
description: >
  Cuts an epic into one-PR stories (at most 300 diff lines and 5 code files), keys them N-N[a-z] only, takes
  decision numbers from an assigned range, and writes specs with mandatory header lines and a done command.
  Use when planning an epic, splitting a story, or writing a story spec.
license: MIT
compatibility: Any coding agent (Claude Code, Codex); optionally a BMAD-style story workflow (create-story); git, grep; a Git forge for the open-PR check.
metadata:
  category: process
  owner: maintainer
  maturity: trial
  added: "2026-10-22"
  updated: "2026-10-22"
  projects: all
  cluster: planning
  leader: "true"
  decided-by: "maintainer, 2026-10"
  review-by: "2027-01-22"
---

# Cut an epic into stories and write the specs

## Environment check

- The project checkout is on a fresh `origin/<default_branch>`; specs are written in a separate worktree and the
  main checkout is left alone.
- `docs/ai/project-profile.yaml` exists (`spec.template`, `spec.check`, `done_command`, `stack`) together with the
  project's spec template (for example a create-story config) and the epic's sprint status file.
- If the project keeps per-module context files (`docs/context/`), they are available.
- Fallback: no template - use the sections listed under Rules; no profile - take the done command from the
  project's CI workflow and put the question to the repository owner in the PR; no assigned decision-number
  range - stop and ask whoever coordinates planning.

## When to use

- Epic planning: the story list, sizes, order and keys.
- The spec of a single story (a create-story workflow or a hand-written spec).
- A story turned out larger than the limit during development: replan it as `<key>a`, `<key>b`.

## Rules

1. **A story is one PR of at most 300 diff lines and 5 code files** (tests and fixtures excluded): one endpoint,
   one screen, one migration or one worker. Anything bigger is cut during planning and never started whole.
2. **Cut earlier** if the story touches more than three modules or adds a second integration point (CI _and_
   a release workflow, a migration _and_ a route).
3. **Keys are `N-N[a-z]` only:** `3-2`, `3-2a`, `3-2b`. Never `3-2a1` or `18-1b1`: a digit after the letter makes
   the story invisible to an unattended dev loop whose parser expects `^(\d+)-(\d+)([a-z]?)-(.+)$`. This is an
   example of a loop constraint - learn your loop's parser. More than 26 sub-stories means a new number.
4. **Complexity follows what the story touches, not its size.** `high`: a migration or schema change, money, a
   transaction with a lock a second actor races for, a published contract. Otherwise `normal`.
   Details and the model per stage: [references/complexity.md](references/complexity.md).
5. **Decision numbers (D-NNN) come only from the assigned range** and against a named tree:
   `numbers from D-nnn, epics.md at <sha>`. Re-read the block after every merge of the default branch into your
   branch. Rules and checks: [references/decision-numbers.md](references/decision-numbers.md).
6. **Mandatory spec lines** (right under the title):
   - `**Status:**` - equals the YAML `status:`; change both in one edit;
   - `**Complexity:** high|normal` plus one sentence naming the item that decided it (or that none did);
   - `**Dev model:** opus|sonnet` - the **literal model name**, not a role: tests and metrics read it.
     `high` maps to `models.heavy` from the profile (default `opus`), `normal` to `models.default` (default
     `sonnet`); the roles "heavy"/"default" appear only in prose;
   - `**Size:** ≤300 lines / ≤5 code files`;
   - `**Modules:**` - modules whose context files to read (if the project keeps them);
   - when `stack: mobile`: `**Analytics:**` - events from the project's closed event catalog, no PII,
     `screen_view` for a new screen, or an explicit "no new events: <why>"; a new feature also needs `**UX:**`
     (a link to the feature's UX notes).
7. **Mandatory sections:** `## Files to touch` (real paths), `## Files not to touch`, `## Contract`, `## Tests`,
   `## Done command` (one command, by default `done_command` from the profile).
8. **The heavy model writes the spec, the default model implements it.** Before development: a readiness check and
   two roundtable passes (at most 4 roles: architect, developer, QA, PM) with the recommendations applied; a spec
   without the second pass's record is not `ready-for-dev`.
9. **Every epic gets a retrospective line** `epic-N-retrospective: required` in the sprint status file (not
   `optional`).
10. **No backward compatibility:** a refactoring spec removes the old code in the same story; the exception is a
    published external API with clients in production.

## How to apply

```sh
# 1. Free numbers: look at open PRs and branches of other sessions, not only the default branch
gh pr list --repo "$FORGE_OWNER/<repo>" --state open --limit 50 --json title -q '.[].title'          # GitHub
curl -sf -H "Authorization: Bearer $GITEA_TOKEN" \
  "$GITEA_URL/api/v1/repos/$FORGE_OWNER/<repo>/pulls?state=open&limit=50" | jq -r '.[].title'         # Gitea
git -C "$CHECKOUT" ls-remote --heads origin | grep -E 'plan|docs/epic' || true
# 2. Story list: key | what | files (<=5) | complexity | done command - before the first spec
# 3. Specs from the project template in a worktree; decision numbers from the assigned range
# 4. Run the checks below; open a docs PR: epic, specs, sprint status
```

Spec header template:

```markdown
# Story 3.2a: <what>

**Status:** ready-for-dev
**Complexity:** normal - no migration, money, race or contract.
**Dev model:** sonnet
**Size:** ≤300 lines / ≤5 code files
**Modules:** blog
**Analytics:** no new events: the story has no screen   <!-- mobile only -->
```

## Verification

```sh
# keys with a digit after the letter - must print nothing
grep -nE '^\s+[0-9]+-[0-9]+[a-z][0-9]' <path>/sprint-status.yaml
# every ready-for-dev spec has the lines and sections (9 matches per spec)
for f in <epic specs>; do grep -c -E '^\*\*(Status|Complexity|Dev model|Size):\*\*|^## (Files to touch|Files not to touch|Contract|Tests|Done command)$' "$f"; done
# decision numbers are not defined twice
git grep -hoE 'D-[0-9]{3,5}' -- <planning dir> | sort | uniq -d
```

Plus the project's own spec check (`spec.check` from the profile, e.g. a spec-check script or a
planning-records test) must be green.

## Exceptions and human stop

- A decision in the spec that changes a published contract, money, permissions or data deletion becomes
  `decision-needed`: stop and ask the owner; do not decide provisionally.
- A story cannot fit the limit without losing its meaning: propose a split to the owner, do not start it whole.
- The decision-number range ran out or overlaps someone else's: stop and request a new range.

## Project profile

`docs/ai/project-profile.yaml`: `stack` (mobile adds the `Analytics`/`UX` lines), `spec.template`, `spec.check`,
`done_command`, `models.heavy` / `models.default` (literals for `**Dev model:**`: `opus` / `sonnet`),
`decisions.file` (where decision numbers are defined).
