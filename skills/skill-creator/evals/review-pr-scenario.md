# Eval: "make a skill about PR review" when review-by-complexity exists

Done scenario for skill-creator. Run by hand or with `claude -p` in a hub checkout.

## Setup

`skills/` contains `review-by-complexity` with `metadata.cluster: review`, `leader: "true"`
(or use the fixture `tools/tests/fixtures/duplicates/skills/` and pass it with `--skills`).

## Prompt

> Make a skill about PR review

## Expected (all points)

1. The agent picks the `skill-creator` skill (a `Skill` call or reading its `SKILL.md` is visible).
2. First thing, it runs `scripts/find-duplicates.py --query "Make a skill about PR review"`; exit code 3.
3. The answer contains the line "similar: review-by-complexity (cluster leader of review)".
4. The answer proposes an **edit** to `review-by-complexity` (which rules/sections to add), not a new skill.
5. `tools/new-skill.sh` was not called and `skills/` has no new directories (`git status` is clean).

## Failure

- A directory `skills/pr-review*` or similar was created.
- The proposal does not name the cluster leader.

The mechanical part (points 2-3) is checked by `tools/tests/test_find_duplicates.py` on fixtures.
