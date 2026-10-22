#!/usr/bin/env bash
# Scaffold a skill card: skills/<name>/{SKILL.md,references/rationale.md,evals/cases.yaml}.
# Usage: tools/new-skill.sh <name> [--category <id>] [--owner <id>]
# Then: tools/validate.py skills/<name>
set -euo pipefail

usage() { echo "usage: $0 <name> [--category <id>] [--owner <id>]" >&2; exit 2; }

repo=$(cd "$(dirname "$0")/.." && pwd)
name=${1:-}; [[ -n $name ]] || usage; shift
category=development
owner=maintainer
while [[ $# -gt 0 ]]; do
  case $1 in
    --category) category=${2:?}; shift 2 ;;
    --owner) owner=${2:?}; shift 2 ;;
    *) usage ;;
  esac
done

if [[ ! $name =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || (( ${#name} > 64 )); then
  echo "name: 1-64 characters, a-z0-9 and single '-', no leading or trailing '-'" >&2; exit 2
fi
for f in categories owners; do
  id=$([[ $f == categories ]] && echo "$category" || echo "$owner")
  if ! grep -Eq "^\s*-\s+id:\s*${id}\s*$" "$repo/catalog/$f.yaml"; then
    echo "no '$id' in catalog/$f.yaml" >&2; exit 2
  fi
done

dir="$repo/skills/$name"
if [[ -e $dir ]]; then echo "already exists: skills/$name" >&2; exit 1; fi

# Similar skills: words of the name found in name/description of existing cards.
if [[ -d $repo/skills ]]; then
  for word in ${name//-/ }; do
    [[ ${#word} -lt 4 ]] && continue
    grep -lEi "^(name|description):.*${word}" "$repo"/skills/*/SKILL.md 2>/dev/null \
      | sed "s|$repo/skills/\(.*\)/SKILL.md|similar: \1 (word '$word'): maybe edit that one instead?|" >&2 || true
  done
fi

today=$(date +%F)
# GNU date first, then BSD date, then python3 as a fallback.
review_by=$(date -d "$today +3 months" +%F 2>/dev/null || date -v+3m +%F 2>/dev/null \
  || python3 -c 'import datetime as d; t=d.date.today(); m=t.month+3; y=t.year+(m-1)//12; m=(m-1)%12+1; print(d.date(y, m, min(t.day, 28)))')
mkdir -p "$dir/references" "$dir/evals"
sed -e "s/__NAME__/$name/g" -e "s/__CATEGORY__/$category/g" -e "s/__OWNER__/$owner/g" \
    -e "s/__DATE__/$today/g" -e "s/__REVIEW_BY__/$review_by/g" \
    "$repo/tools/templates/SKILL.md" > "$dir/SKILL.md"
cat > "$dir/references/rationale.md" <<EOF
# $name: rationale

<!-- History of the rule, dated decisions, links to retrospectives and incidents. Loaded on demand. -->
EOF
cat > "$dir/evals/cases.yaml" <<EOF
# 2-5 scenarios: the happy path and an edge case. Prompt -> what the agent should do.
cases:
  - prompt: "<a request on which the skill should trigger>"
    expect: "<what the agent does following the skill>"
EOF
echo "created skills/$name (maturity: draft). Next: tools/validate.py skills/$name"
