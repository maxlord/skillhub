---
name: __NAME__
description: >
  Guides __NAME__: one sentence on what the skill does.
  Use when <the situation in which the agent should pick this skill>.
license: MIT
compatibility: Claude Code, Codex
metadata:
  category: __CATEGORY__
  owner: __OWNER__
  maturity: draft
  added: "__DATE__"
  updated: "__DATE__"
  projects: all
  source: ""
  review-by: "__REVIEW_BY__"
---

# __NAME__

<!-- Skill card: body at most 300 lines; history and rationale go to references/.
     Repo-specific values come from the project profile (docs/ai/project-profile.yaml); hosts, ports and
     accounts come from an environment profile kept outside the hub. Secrets: reference by file name
     only: `$SECRETS_DIR/<name>`, never the content. -->

## Environment check

- What must exist: `docs/ai/project-profile.yaml` in the repo, credentials for the git host (for example `~/.netrc`).
- Fallback if something is missing: <what to do, or "stop for a human">.

## When to use

- <situation 1>

## Rules

1. <rule, in the imperative>

## How to apply

```sh
# commands
```

## Verification

- <how to prove it is done>

## Exceptions and human stop

- <when to stop and wait for the owner>

## Project profile

- Keys from `docs/ai/project-profile.yaml`: <which ones>.

Why it works this way: [references/rationale.md](references/rationale.md).
