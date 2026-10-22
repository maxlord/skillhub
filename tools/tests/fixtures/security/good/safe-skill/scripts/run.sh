#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT  # security-lint: allow danger-rm-rf - own temporary directory
curl -sf -H "PRIVATE-TOKEN: ${GIT_TOKEN:?}" "${GIT_URL:?}/api/v1/version"
