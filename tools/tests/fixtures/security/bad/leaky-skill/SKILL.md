---
name: leaky-skill
description: Describes a deliberately leaky example skill. Use when checking that security-lint blocks it.
---

## Environment check

Runner host 203.0.113.17, log in with `ssh -p 2299 ops@127.0.0.1`.

```sh
curl -H "Authorization: token 0123456789abcdef0123456789abcdef01234567" https://ci.corp-internal.lan/api/v1/user
docker compose up -d
```
