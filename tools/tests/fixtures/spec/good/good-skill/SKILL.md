---
name: good-skill
description: >
  Guides an example skill card for spec-lint tests.
  Use when checking the linter against a good skill.
license: MIT
compatibility: Claude Code, Codex
metadata:
  category: development
  owner: maintainer
  maturity: stable
  added: 2026-10-22
  updated: "2026-10-22"
  projects: all
  cluster: example
  leader: "true"
  review-by: 2027-01-22
---

# Good skill

## Environment check

- Needs `~/.netrc`; if it is missing, stop for a human.

## When to use

When you check the linter.

## Rules

1. Do it well.

## How to apply

Details: [rationale](references/rationale.md) and `references/rationale.md`.

## Verification

`tools/spec_lint.py skills/good-skill`
