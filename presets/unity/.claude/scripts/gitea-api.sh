#!/usr/bin/env bash
# Gitea API interaction script
# Used by Feature Agent / Review Agent to interact with a Gitea instance.
#
# Required environment variables:
#   GITEA_TOKEN  - Gitea API token
#
# Optional environment variables:
#   GITEA_URL    - Gitea instance URL (default: {gitea-url})
#   GITEA_OWNER  - Repository owner (default: {gitea-owner})
#   GITEA_REPO   - Repository name (default: {gitea-repo})

set -euo pipefail

# --- Force Python UTF-8 (Windows defaults to GBK, causing CJK garbling) ---
export PYTHONUTF8=1

# --- Defaults (placeholders replaced by /init-project) ---
GITEA_URL="${GITEA_URL:-{gitea-url}}"
GITEA_OWNER="${GITEA_OWNER:-{gitea-owner}}"
GITEA_REPO="${GITEA_REPO:-{gitea-repo}}"
API_BASE="${GITEA_URL}/api/v1"

# --- Temp file management ---
TMPFILE=""
cleanup() { [[ -n "$TMPFILE" ]] && rm -f "$TMPFILE" || true; }
trap cleanup EXIT

# --- Token check ---
check_token() {
  if [[ -z "${GITEA_TOKEN:-}" ]]; then
    echo "ERROR: GITEA_TOKEN environment variable is not set" >&2
    echo "Run: export GITEA_TOKEN=<your-token>" >&2
    exit 1
  fi
}

# --- JSON builder (via Python for UTF-8 safety) ---
build_json() {
  TMPFILE=$(python -c "import tempfile, os; print(os.path.join(tempfile.gettempdir(), 'gitea_api_payload.json'))")
  python -c "
import json, sys
pairs = []
i = 1
while i < len(sys.argv):
    pairs.append((sys.argv[i], sys.argv[i+1]))
    i += 2
data = dict(pairs)
with open(r'$TMPFILE', 'wb') as f:
    f.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
" "$@"
  echo "$TMPFILE"
}

# --- HTTP helpers (stdlib only — no curl/requests dependency) ---
api_get() {
  local endpoint="$1"
  python << PYEOF
import urllib.request, sys
req = urllib.request.Request(
    "${API_BASE}${endpoint}",
    headers={"Authorization": "token ${GITEA_TOKEN}", "Accept": "application/json"}
)
with urllib.request.urlopen(req) as resp:
    sys.stdout.buffer.write(resp.read())
PYEOF
}

api_post() {
  local method="$1"
  local endpoint="$2"
  local json_file="$3"

  python << PYEOF
import urllib.request, json, sys

with open(r'${json_file}', 'rb') as f:
    payload = f.read()

req = urllib.request.Request(
    "${API_BASE}${endpoint}",
    data=payload,
    method="${method}",
    headers={
        "Authorization": "token ${GITEA_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json"
    }
)
with urllib.request.urlopen(req) as resp:
    sys.stdout.buffer.write(resp.read())
PYEOF
}

# --- Command: Create PR ---
create_pr() {
  local title="$1"
  local head="$2"
  local base="${3:-master}"
  local body="${4:-}"

  check_token

  local json_file
  json_file=$(build_json "title" "$title" "head" "$head" "base" "$base" "body" "$body")

  local response
  response=$(api_post POST "/repos/${GITEA_OWNER}/${GITEA_REPO}/pulls" "$json_file")

  local pr_number
  pr_number=$(echo "$response" | python -c 'import json,sys; print(json.load(sys.stdin).get("number","ERROR"))' 2>/dev/null)

  if [[ "$pr_number" == "ERROR" ]] || [[ -z "$pr_number" ]]; then
    echo "ERROR: Failed to create PR" >&2
    echo "$response" >&2
    return 1
  fi

  echo "PR #${pr_number} created: ${GITEA_URL}/${GITEA_OWNER}/${GITEA_REPO}/pulls/${pr_number}"
  echo "$pr_number"
}

# --- Command: Comment on PR ---
comment_pr() {
  local pr_number="$1"
  local body="$2"

  check_token

  local json_file
  json_file=$(build_json "body" "$body")

  api_post POST "/repos/${GITEA_OWNER}/${GITEA_REPO}/issues/${pr_number}/comments" "$json_file" > /dev/null
  echo "Comment added to PR #${pr_number}"
}

# --- Command: Review PR ---
review_pr() {
  local pr_number="$1"
  local body="$2"
  local event="${3:-COMMENT}" # APPROVED | REQUEST_CHANGES | COMMENT

  check_token

  local json_file
  json_file=$(build_json "body" "$body" "event" "$event")

  local response
  response=$(api_post POST "/repos/${GITEA_OWNER}/${GITEA_REPO}/pulls/${pr_number}/reviews" "$json_file" 2>&1) || {
    echo "ERROR: Review API request failed" >&2
    echo "Response: ${response}" >&2
    echo "Falling back to comment-pr..." >&2
    comment_pr "$pr_number" "$body"
    return 1
  }

  echo "Review submitted on PR #${pr_number} (${event})"
}

# --- Command: Get PR details ---
get_pr() {
  local pr_number="$1"

  check_token

  local response
  response=$(api_get "/repos/${GITEA_OWNER}/${GITEA_REPO}/pulls/${pr_number}")

  echo "$response" | python -c "
import json, sys
pr = json.load(sys.stdin)
num = pr['number']
title = pr['title']
state = pr['state']
head = pr['head']['ref']
base = pr['base']['ref']
user = pr['user']['login']
body = pr.get('body', '') or ''
labels = ', '.join(l['name'] for l in pr.get('labels', []))
print(f'PR #{num}: {title}')
print(f'State: {state} | Author: {user}')
print(f'Branch: {head} -> {base}')
if labels:
    print(f'Labels: {labels}')
print('---')
print(body)
" 2>/dev/null || echo "$response"
}

# --- Command: Get PR reviews ---
get_pr_reviews() {
  local pr_number="$1"

  check_token

  local response
  response=$(api_get "/repos/${GITEA_OWNER}/${GITEA_REPO}/pulls/${pr_number}/reviews")

  echo "$response" | python -c "
import json, sys
reviews = json.load(sys.stdin)
if not reviews:
    print('No reviews yet')
    sys.exit(0)
for r in reviews:
    rid = r['id']
    user = r['user']['login']
    state = r.get('state', 'COMMENT')
    body = r.get('body', '') or ''
    print(f'Review #{rid} by {user} [{state}]')
    if body.strip():
        print(body)
    print('---')
" 2>/dev/null || echo "$response"
}

# --- Command: Get PR comments ---
get_pr_comments() {
  local pr_number="$1"

  check_token

  local response
  response=$(api_get "/repos/${GITEA_OWNER}/${GITEA_REPO}/issues/${pr_number}/comments")

  echo "$response" | python -c "
import json, sys
comments = json.load(sys.stdin)
if not comments:
    print('No comments yet')
    sys.exit(0)
for c in comments:
    cid = c['id']
    user = c['user']['login']
    created = c['created_at'][:10]
    body = c.get('body', '') or ''
    print(f'Comment #{cid} by {user} ({created})')
    print(body)
    print('---')
" 2>/dev/null || echo "$response"
}

# --- Command: Get Issue ---
get_issue() {
  local issue_number="$1"

  check_token

  local response
  response=$(api_get "/repos/${GITEA_OWNER}/${GITEA_REPO}/issues/${issue_number}")

  echo "$response" | python -c "
import json, sys
data = json.load(sys.stdin)
num = data['number']
title = data['title']
state = data['state']
labels = ', '.join(l['name'] for l in data.get('labels', []))
body = data.get('body', '')
print(f'Issue #{num}: {title}')
print(f'State: {state}')
print(f'Labels: {labels}')
print('---')
print(body)
" 2>/dev/null || echo "$response"
}

# --- Command: Update Issue state ---
update_issue_state() {
  local issue_number="$1"
  local state="$2" # open | closed

  check_token

  local json_file
  json_file=$(build_json "state" "$state")

  api_post PATCH "/repos/${GITEA_OWNER}/${GITEA_REPO}/issues/${issue_number}" "$json_file" > /dev/null
  echo "Issue #${issue_number} state updated to ${state}"
}

# --- Command: List PRs ---
list_prs() {
  local state="${1:-open}" # open | closed | all

  check_token

  local response
  response=$(api_get "/repos/${GITEA_OWNER}/${GITEA_REPO}/pulls?state=${state}&limit=20")

  echo "$response" | python -c "
import json, sys
prs = json.load(sys.stdin)
for pr in prs:
    num = pr['number']
    state = pr['state']
    title = pr['title']
    head = pr['head']['ref']
    base = pr['base']['ref']
    print(f'#{num} [{state}] {title} ({head} -> {base})')
" 2>/dev/null || echo "$response"
}

# --- Entry point ---
usage() {
  cat <<'USAGE'
Usage: bash gitea-api.sh <command> [args...]

Commands:
  create-pr <title> <head-branch> [base-branch] [body]
    Create a Pull Request

  comment-pr <pr-number> <body>
    Add a comment to a PR

  review-pr <pr-number> <body> [APPROVED|REQUEST_CHANGES|COMMENT]
    Submit a PR review (default: COMMENT)

  get-pr <pr-number>
    Get PR details

  get-pr-reviews <pr-number>
    Get all reviews for a PR

  get-pr-comments <pr-number>
    Get PR comments

  get-issue <issue-number>
    Get issue details

  update-issue <issue-number> <open|closed>
    Update issue state

  list-prs [open|closed|all]
    List Pull Requests

Environment variables:
  GITEA_TOKEN  (required) API token
  GITEA_URL    (optional) Gitea instance URL
  GITEA_OWNER  (optional) Repository owner
  GITEA_REPO   (optional) Repository name
USAGE
}

case "${1:-}" in
  create-pr)       shift; create_pr "$@" ;;
  comment-pr)      shift; comment_pr "$@" ;;
  review-pr)       shift; review_pr "$@" ;;
  get-pr)          shift; get_pr "$@" ;;
  get-pr-reviews)  shift; get_pr_reviews "$@" ;;
  get-pr-comments) shift; get_pr_comments "$@" ;;
  get-issue)       shift; get_issue "$@" ;;
  update-issue)    shift; update_issue_state "$@" ;;
  list-prs)        shift; list_prs "$@" ;;
  -h|--help|"") usage ;;
  *)
    echo "ERROR: Unknown command '$1'" >&2
    usage >&2
    exit 1
    ;;
esac
