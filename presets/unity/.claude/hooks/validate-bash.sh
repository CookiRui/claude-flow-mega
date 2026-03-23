#!/usr/bin/env bash
# validate-bash.sh — PreToolUse hook: Block dangerous shell commands
#
# Usage: Configure as a Claude Code PreToolUse Hook
#   .claude/settings.json:
#   {
#     "hooks": {
#       "PreToolUse": [
#         { "matcher": "Bash", "command": "bash .claude/hooks/validate-bash.sh" }
#       ]
#     }
#   }
#
# Exit codes:
#   0  — command is safe, proceed
#   2  — command is blocked (Claude Code will reject the tool call)

set -euo pipefail

# ---------------------------------------------------------------------------
# Extract the "command" field from the tool input JSON on stdin
# ---------------------------------------------------------------------------

input=$(cat)
command=$(echo "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)

[ -z "$command" ] && exit 0

# ---------------------------------------------------------------------------
# BLOCKED PATTERNS
# ---------------------------------------------------------------------------

# BLOCK: Destroying Unity Library/ cache (very long rebuild)
# {unity-project-dir} — replace with your Unity project directory if not at repo root
if echo "$command" | grep -qEi 'rm\s+.*(-[a-zA-Z]*f|--force).*Library|rm\s+.*Library/'; then
  echo "BLOCKED: Deleting Library/ would require a very long reimport. Use Unity Editor to resolve issues." >&2
  exit 2
fi

# BLOCK: git clean -f (may delete untracked Unity assets and .meta files)
if echo "$command" | grep -qEi 'git\s+clean\s+.*(-[a-zA-Z]*f|--force)'; then
  echo "BLOCKED: git clean -f/--force may delete untracked Unity assets and .meta files." >&2
  exit 2
fi

# BLOCK: git reset --hard (destroys uncommitted work)
if echo "$command" | grep -qEi 'git\s+reset\s+--hard'; then
  echo "BLOCKED: git reset --hard discards all uncommitted changes. Use targeted git restore instead." >&2
  exit 2
fi

# BLOCK: Force push (rewrites remote history)
if echo "$command" | grep -qEi 'git\s+push\s+.*(-f|--force)'; then
  echo "BLOCKED: git push --force rewrites remote history. Use non-force push." >&2
  exit 2
fi

# BLOCK: git checkout . (discards all working tree changes)
if echo "$command" | grep -qEi 'git\s+checkout\s+\.'; then
  echo "BLOCKED: git checkout . discards all working tree changes. Use targeted git restore <file> instead." >&2
  exit 2
fi

exit 0
