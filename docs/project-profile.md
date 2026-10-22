# Project profile: the portable contract

Skills in this hub never hard-code values of a particular repository or environment.
Each consuming repository keeps them in **`docs/ai/project-profile.yaml`**, and a skill reads the keys it
needs in its first section ("Environment check"). A key that is missing triggers the skill's documented
fallback — usually "ask the repository owner", never "guess".

Hosts, ports, accounts and secrets do not belong in the profile either: they live in an environment profile
outside the repository, and secrets are referenced by file name only (`$SECRETS_DIR/<name>`), never by value.

## Example

```yaml
# docs/ai/project-profile.yaml
repo: my-org/backend
forge: gitea                    # gitea | github — selects the API examples in skills
default_branch: dev
stack: nestjs                   # nestjs | kmp-mobile | go | web | ...; mobile enables Analytics/UX spec lines

merge_style:
  story: merge                  # merge | squash | rebase — ordinary story PRs
  loop: fast-forward-only       # landings produced by an unattended dev loop
  release: merge                # release PR into main: always a merge commit, never squash

ci:
  pr_check: ci/check            # status context that must be green on the exact PR head
  epic: ci/epic                 # heavier pipeline run once per epic (optional)

done_command: npm run verify    # the one command a story's spec names as "done"
spec:
  template: _bmad/custom/create-story.toml
  check: scripts/spec-check.sh
decisions:
  file: docs/planning/decisions.md   # where D-NNN decision numbers are defined

models:
  heavy: opus                   # spec writing, high-complexity stories
  default: sonnet               # implementation and review

review:
  ledger: docs/planning/deferred-work.md

retro:
  dir: docs/retro
sprint_status: docs/planning/sprint-status.yaml
docs:
  architecture: docs/architecture/overview.md

release:
  branch: release/vX            # release/vX — dedicated branch; dev — PR straight dev → main
  tag: workflow                 # workflow — a release workflow tags main; push — annotated tag on a named sha
  workflow: release.yml
  deploy: deploy.yml
  deploy_window: "not at night" # optional
  version_files: [package.json]
  scripts:
    prepare: scripts/release/prepare.sh
    sync: scripts/release/sync-main-to-dev.sh
```

## Keys by skill

| Skill | Keys |
|---|---|
| `feature-branch-flow` | `repo`, `forge`, `default_branch`, `merge_style.*`, `ci.pr_check` |
| `story-spec` | `stack`, `spec.*`, `done_command`, `models.*`, `decisions.file` |
| `review-by-complexity` | `repo`, `ci.pr_check`, `ci.epic`, `review.ledger`, `merge_style` |
| `retrospective` | `retro.dir`, `sprint_status`, `review.ledger`, `docs.architecture` |
| `merge-and-release` | `repo`, `merge_style.*`, `release.*`, `ci.pr_check` |
| `skill-creator` | none — runs inside the hub |
