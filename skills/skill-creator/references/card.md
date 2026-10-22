# Hub skill card

| Field | Rule |
|---|---|
| `name` | 1-64 chars of `a-z0-9-`, no `--`, equal to the directory name; optional prefixes such as `stack-`, `infra-` |
| `description` | at most 400 characters, starts with an action verb: what it does + "Use when..." |
| `license` | `MIT` |
| `compatibility` | at most 500 characters: agents, versions, what the environment needs |
| `metadata.category` | an id from `catalog/categories.yaml`; the category selects the plugin (`plugin`) |
| `metadata.owner` | an id from `catalog/owners.yaml` |
| `metadata.maturity` | new skills start as `draft`; `trial` after the first runs; `stable` after a retrospective |
| `metadata.added` / `updated` | `YYYY-MM-DD`; `updated` = date of the last catalog commit |
| `metadata.projects` | repos, comma-separated, or `all` |
| `metadata.depends` | hub skills only; the body must not rely on their text |
| `metadata.cluster` / `leader` | cluster of similar skills; exactly one `leader: "true"` |
| `metadata.decided-by` | the decisions behind the practice, with dates |
| `metadata.review-by` | `added` + 3 months |

There is no `version` field. All `metadata` values are strings (dates in quotes).

Body sections in order: "Environment check" (with a fallback), "When to use", "Rules", "How to apply",
"Verification", "Exceptions and human stop", "Project profile". At most 300 lines and about 4000 tokens; history
and "why" go to `references/`, links one level deep. Scripts live in the skill's `scripts/`.

The security flag is written by CI, not by the author: `blocked` on a secret, a token in `curl`/`wget`, an
unknown host or internal address, a request to paste a token into chat, or a dangerous operation without a
stop point. A `blocked` skill never reaches the plugins.
