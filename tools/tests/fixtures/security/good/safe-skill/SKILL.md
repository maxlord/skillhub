---
name: safe-skill
description: Describes a safe example skill. Use when testing security-lint.
---

## Environment check

- Needs `~/.netrc`; the git host token lives in `$SECRETS_DIR/<name>`, its content is never shown.
- The runner host is `hosts.runners[]` from your infrastructure profile.

## How to apply

```sh
curl -sfn https://git.example.org/api/v1/repos/example-org/example-repo/pulls
curl -sf -H "Authorization: token $GIT_TOKEN" "$GIT_URL/api/v1/user"
curl -sf -H "Authorization: token $(cat "$TOKEN_FILE")" "$GIT_URL/api/v1/user"
git clone git@github.com:example-org/example-repo.git
ssh "$RUNNER_HOST" docker ps
ssh -p 22 "$USER@$RUNNER_HOST" uptime
export APP_IMAGE=$(docker inspect -f '{{.Config.Image}}' api)
docker compose up -d api
docker image prune -f
```

Human stop: delete the directory only after the owner confirms:
`rm -rf "$WORKDIR"`.

Files: `SKILL.md`, `scripts/run.sh`, `config.toml`, `package.json`, version v0.17.0, spec https://agentskills.io/specification.
Commit email: noreply@anthropic.com. App port `:8080` inside the container.
