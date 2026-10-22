---
name: skill-creator
description: >
  Creates a skill for the hub on top of a generic skill-creator: first searches for similar skills (name,
  description, cluster, body phrases) and proposes editing the cluster leader, then scaffolds a new one by the hub
  card and validates locally. Use when asked to "make a skill about..." or to move a practice into the hub.
license: MIT
compatibility: Any coding agent (Claude Code, Codex); Python 3.10+ (stdlib only); a checkout of the skills hub; a generic skill-creator skill is optional.
metadata:
  category: development
  owner: maintainer
  maturity: trial
  added: "2026-10-22"
  updated: "2026-10-22"
  projects: all
  cluster: skillhub
  leader: "false"
  decided-by: "maintainer, 2026-10"
  review-by: "2027-01-22"
---

# Create a hub skill without duplicates

## Environment check

- The current directory is a checkout of the skills hub (it has `skills/`, `tools/validate.py`, `tools/new-skill.sh`).
- `python3` 3.10+; this skill's `scripts/find-duplicates.py` uses only the stdlib.
- A generic `skill-creator` skill is desirable but not required.
- Fallback: no checkout - clone the hub repository and work in it; no generic `skill-creator` - write the body
  yourself from `tools/templates/SKILL.md` and `references/card.md`; no `python3` - human stop.

## When to use

- Asked to "make a skill about...", "move this into the hub", "turn this practice into a skill".
- A retrospective or a `candidate` issue proposes a new practice for the hub.
- Do not use to edit a known skill by name - edit it directly.

## Rules

1. **Duplicates first, creation second.** Before creating any file, run `scripts/find-duplicates.py` with the
   user's request and the intended name.
2. If similar skills exist, **do not create a new one.** Answer with "similar: X (cluster leader), Y" and propose
   an edit to the cluster leader (or to the found skill if there is no cluster): which sections and rules to add.
3. A new skill despite similar ones only if a human explicitly confirmed the practice is different; write the
   reason into the new skill's a rationale note under its references directory, keep `metadata.cluster` the same and set `leader: "false"`.
4. Scaffold only with `tools/new-skill.sh <name> --category <id>`; the card follows
   [references/card.md](references/card.md): `description` at most 400 characters, starts with a verb and
   contains "Use when...".
5. Drive the content, evals and the `description` wording through the generic `skill-creator` (its interview,
   draft and test prompts) if available. Do not change its directory format: files live in `skills/<name>/`,
   evals in `evals/cases.yaml`.
6. No repository or environment values, secrets or addresses: use the project profile, and refer to secrets as
   `$SECRETS_DIR/<name>` by reference only.
7. Done only when the local `tools/validate.py` is green and the plugin copies are built by `tools/build-plugins.py`.
   Contribution workflow details are in the hub's CONTRIBUTING.md.

## How to apply

```sh
python3 "${CLAUDE_SKILL_DIR:-skills/skill-creator}/scripts/find-duplicates.py" \
  --query "<user request>" --name <intended-name>
# exit 3 - similar skills exist: show the list and propose editing the leader; exit 0 - none
tools/new-skill.sh <name> --category <id>      # only on exit 0 or an explicit "yes, it is different"
# generic skill-creator: interview -> SKILL.md body by the card sections -> evals/cases.yaml (2-5 scenarios)
python3 tools/validate.py skills/<name>        # spec lint + security lint, as in CI
python3 tools/build-plugins.py && python3 tools/build-plugins.py --check
```

Answer when similar skills are found, in short:

```
Similar: review-by-complexity (cluster leader of review), review-checklist.
I suggest not adding a new skill but extending review-by-complexity: <which rules/sections>.
A separate skill only if the practice is different; tell me how.
```

## Verification

- The answer to the user contains the `find-duplicates.py` output (or "no similar skills").
- For a new skill: `python3 tools/validate.py skills/<name>` exits 0 with `blocked 0`; `build-plugins.py --check` says `ok`.
- The PR contains the output of these commands; the branch starts from `origin/<default_branch>`.

## Exceptions and human stop

- Several clusters match, or the cluster has no leader: show them and ask who should become the leader.
- A skill about production, money or permissions: a PR is fine, merging waits for the owner.
- `security-lint` reports `blocked` and the value cannot be moved into the profile: human stop.

## Project profile

- Runs inside the hub, so no project profile is needed. Values for the future skill are keys of a project's
  `docs/ai/project-profile.yaml`; the skill text names only the keys.

The card and its fields: [references/card.md](references/card.md).
