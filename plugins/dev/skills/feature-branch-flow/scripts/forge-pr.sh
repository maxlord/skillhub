#!/usr/bin/env bash
# Pull requests on Gitea or GitHub for agents: open, status, merge, close, comment.
#   forge-pr.sh <repo> open <head> <base> <title> [<body-file>]   - open a PR, prints its number
#   forge-pr.sh <repo> status <N>                                  - state/merged/mergeable/head sha + CI statuses of that head
#   forge-pr.sh <repo> merge <N> <merge|squash|rebase|fast-forward-only>  - merge the exact head, delete the branch
#   forge-pr.sh <repo> close <N> "<comment>"                       - comment, close, delete the PR branch
#   forge-pr.sh <repo> comment <N> "<comment>"
# Environment: FORGE=gitea|github (default gitea), FORGE_OWNER (org or user, required),
#   gitea: GITEA_URL (required, no default; base URL of your instance), auth via ~/.netrc (curl -n)
#   github: GH_TOKEN (sent as a Bearer header), API at api.github.com
#   PR_SIGNATURE: optional text appended to comments; FORGE_REPOS: optional allow-list of repos (space separated)
# The merge style is never guessed: take it from docs/ai/project-profile.yaml (merge_style).
set -euo pipefail
usage(){ sed -n '2,11p' "$0" >&2; exit 2; }
[[ $# -ge 3 ]] || usage
repo=$1 action=$2; shift 2
FORGE=${FORGE:-gitea}
: "${FORGE_OWNER:?set FORGE_OWNER}"
[[ $repo =~ ^[A-Za-z0-9._-]+$ ]] || { echo "bad repo name: $repo" >&2; exit 2; }
if [[ -n ${FORGE_REPOS:-} && " $FORGE_REPOS " != *" $repo "* ]]; then echo "repo not in FORGE_REPOS: $repo" >&2; exit 2; fi
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }
case $FORGE in
  gitea)  : "${GITEA_URL:?set GITEA_URL}"; ROOT=$GITEA_URL/api/v1/repos/$FORGE_OWNER/$repo
          c(){ curl -sn -H 'Content-Type: application/json' "$@"; } ;;
  github) : "${GH_TOKEN:?set GH_TOKEN}"; ROOT=https://api.github.com/repos/$FORGE_OWNER/$repo
          c(){ curl -s -H "Authorization: Bearer $GH_TOKEN" -H 'Accept: application/vnd.github+json' "$@"; } ;;
  *) echo "FORGE must be gitea or github" >&2; exit 2 ;;
esac
SIGN=${PR_SIGNATURE:+$'\n\n'$PR_SIGNATURE}
num(){ [[ $1 =~ ^[0-9]+$ ]] || { echo "bad PR number: $1" >&2; exit 2; }; }
get(){ c --fail "$ROOT/$1"; }
post_comment(){ c --fail -X POST "$ROOT/issues/$1/comments" -d "$(jq -n --arg b "$2$SIGN" '{body:$b}')" >/dev/null; }
del_branch(){
  local r; r=$(jq -rn --arg r "$1" '$r|@uri')
  if [[ $FORGE == gitea ]]; then c --fail -X DELETE "$ROOT/branches/$r" >/dev/null
  else c --fail -X DELETE "$ROOT/git/refs/heads/$1" >/dev/null; fi
}

case $action in
  open)
    [[ $# -ge 3 ]] || usage
    head=$1 base=$2 title=$3 body=""
    [[ -n ${4:-} ]] && body=$(cat "$4")
    c --fail -X POST "$ROOT/pulls" \
      -d "$(jq -n --arg h "$head" --arg b "$base" --arg t "$title" --arg d "$body" '{head:$h,base:$b,title:$t,body:$d}')" \
      | jq -r '"#\(.number) \(.html_url)"' ;;
  status)
    n=$1; num "$n"
    pr=$(get pulls/$n); sha=$(jq -r .head.sha <<<"$pr")
    jq -r '"#\(.number) state=\(.state) merged=\(.merged) mergeable=\(.mergeable) head=\(.head.sha) base=\(.base.ref)"' <<<"$pr"
    get commits/$sha/status | jq -r '"ci=\(.state)", (.statuses[]? | "  \(.context): \(.status // .state)")' ;;
  merge)
    n=$1 style=${2:-}; num "$n"
    case $style in merge|squash|rebase|fast-forward-only) ;; *) echo "style: merge|squash|rebase|fast-forward-only (from the project profile)" >&2; exit 2;; esac
    [[ $FORGE == github && $style == fast-forward-only ]] && { echo "GitHub has no fast-forward-only merge via API; push the branch tip to the base by hand" >&2; exit 2; }
    mergeable=false
    for _ in $(seq 10); do
      [[ $(get pulls/$n | jq -r .mergeable) == true ]] && { mergeable=true; break; }; sleep 3
    done
    pr=$(get pulls/$n); sha=$(jq -r .head.sha <<<"$pr"); ref=$(jq -r .head.ref <<<"$pr")
    out=$(mktemp); trap 'rm -f "$out"' EXIT
    if [[ $FORGE == gitea ]]; then
      code=$(c -o "$out" -w '%{http_code}' -X POST "$ROOT/pulls/$n/merge" \
        -d "$(jq -n --arg s "$style" --arg h "$sha" '{Do:$s,head_commit_id:$h,delete_branch_after_merge:true}')")
    else
      code=$(c -o "$out" -w '%{http_code}' -X PUT "$ROOT/pulls/$n/merge" \
        -d "$(jq -n --arg s "$style" --arg h "$sha" '{merge_method:$s,sha:$h}')")
    fi
    sleep 2; merged=$(get pulls/$n | jq -r .merged)
    [[ $FORGE == github && $merged == true ]] && del_branch "$ref" || true
    echo "#$n $repo merge $style head=$sha mergeable=$mergeable http=$code merged=$merged $(head -c 300 "$out")"
    [[ $merged == true ]] ;;
  close)
    n=$1; num "$n"
    [[ -n ${2:-} ]] && post_comment "$n" "$2"
    pr=$(get pulls/$n)
    ref=$(jq -r .head.ref <<<"$pr") base=$(jq -r .base.ref <<<"$pr")
    default=$(get "" | jq -r .default_branch)
    echo "#$n $repo $(c --fail -X PATCH "$ROOT/pulls/$n" -d '{"state":"closed"}' | jq -r .state)"
    if [[ $ref == refs/* || $ref == "$base" || $ref == "$default" || $ref == main ]]; then
      echo "branch $ref kept (base/default/main or already deleted)"
    else
      del_branch "$ref" && echo "branch $ref deleted"
    fi ;;
  comment)
    n=$1; num "$n"; [[ -n ${2:-} ]] || usage
    post_comment "$n" "$2"; echo "#$n $repo commented" ;;
  *) usage ;;
esac
