# Contributing

This hub holds engineering practices as Agent Skills. Every change - a new skill or a fix to an existing one -
follows the same path.

## 1. Find a similar skill first

Duplicates are the main disease of skill hubs: two skills about the same thing drift apart and the agent picks
one at random. Before adding anything, search by `name`, `description`, `metadata.cluster` and body phrases:

```sh
python3 skills/skill-creator/scripts/find-duplicates.py --query "<what the skill is about>" --name <intended-name>
# exit 3: similar skills exist - edit the cluster leader (metadata.leader: "true") instead
```

If a similar skill exists, edit it (or the cluster leader). Add a new skill to an existing cluster only when the
practice is genuinely different, with `leader: "false"` and the reason in a note under `references/`.

## 2. Scaffold

```sh
git fetch origin && git switch -c feat/<slug> origin/<default-branch>
tools/new-skill.sh <name> --category <id>
```

`<name>` is `a-z0-9-` (1-64 chars, no `--`) and equals the directory name; stack or infrastructure skills may use
a `stack-` or `infra-` prefix. The category selects the plugin through the `plugin` field in
`catalog/categories.yaml`. A new category without a plugin needs the plugin first
(`.claude-plugin/marketplace.json` and `plugins/<plugin>/.claude-plugin/plugin.json`).

## 3. Card rules

- `description`: at most 400 characters, starts with an action verb (Cuts, Closes, Creates...), says what the skill
  does and contains "Use when...".
- `license: MIT`; `compatibility` at most 500 characters (agents, versions, environment needs).
- `metadata` values are all strings: `category`, `owner`, `maturity` (`draft` -> `trial` -> `stable`), `added`,
  `updated` (date of the last commit touching the skill, quoted), `projects`, `cluster`, `leader`, `decided-by`,
  `review-by` (`added` + 3 months). Optional `depends` names hub skills only.
- There is no `version` field: consumers always get the latest from the main branch; history is `git log`.

Details: `skills/skill-creator/references/card.md`.

## 4. Body sections

At most 300 lines and about 4000 tokens, in this order:

1. `## Environment check` - what must be true, with a fallback when it is not
2. `## When to use`
3. `## Rules`
4. `## How to apply`
5. `## Verification`
6. `## Exceptions and human stop`
7. `## Project profile` - the profile keys the skill reads

History and "why" go to `references/` (links one level deep). Evals go to `evals/`.

## 5. No repository or environment values

A skill never hard-codes a repo name, merge style, CI job, host, port or account. It reads them from the consuming
repository's `docs/ai/project-profile.yaml` (see `docs/project-profile.md`) and names only the keys. Hosts and
accounts live in an environment profile outside the repository; secrets are referenced by file name only
(`$SECRETS_DIR/<name>`), never by value. Show forge commands in both variants (`gh ...` and
`curl -H "Authorization: Bearer $TOKEN" "$GITEA_URL/..."`) using environment variables only. If you need a new
profile key, add it to the example and the table in `docs/project-profile.md`.

## 6. Scripts

A skill's scripts live in its own `scripts/` directory, stdlib-only where possible, and are referenced relative to
the skill.

## 7. Never hand-edit plugin copies

`plugins/*/skills/` are generated from `skills/`. Edit `skills/<name>` and rebuild:

```sh
python3 tools/build-plugins.py
```

A hand-edited copy fails CI.

## 8. Validate

```sh
python3 tools/validate.py skills/<name>       # spec lint + security lint: 0 errors, blocked 0
python3 tools/build-plugins.py --check        # prints ok
python3 -m unittest discover -s tools/tests
```

A `blocked` security finding is real: move the value into the project profile or a secret reference, do not
suppress it.

## 9. One branch, one PR

One change per branch off the default branch and one pull request into it. Put the output of the commands above
in the PR description. A skill about production, money or permissions can be opened as a PR, but its merge waits
for an explicit maintainer decision.

## Why it's built this way

- **One source.** A skill lives in `skills/`; plugins receive copies by build. Symlinks may not survive a
  marketplace clone, while a copy is visible in the diff. A hand-edited copy breaks CI.
- **Similar first.** Duplicates make agents pick an arbitrary one; hence clusters and leaders.
- **No repo values.** The catalog is public, so secrets and internal addresses never enter it; the security lint
  enforces it and a `blocked` skill is excluded from the plugins.
- **No versions.** Always the latest from the main branch; history is the `git log` of the skill directory.
