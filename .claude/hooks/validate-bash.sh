#!/bin/bash
# validate-bash.sh — PreToolUse hook that blocks dangerous shell commands
#
# Usage: Configure as a Claude Code PreToolUse Hook
#   .claude/settings.json:
#   {
#     "hooks": {
#       "PreToolUse": [
#         { "matcher": "Bash", "hooks": [{ "type": "command", "command": "bash .claude/hooks/validate-bash.sh" }] }
#       ]
#     }
#   }

set -euo pipefail

# ---------------------------------------------------------------------------
# DANGEROUS COMMAND PATTERNS
# ---------------------------------------------------------------------------

DANGEROUS_PATTERNS=(
    # Destructive file operations
    'rm\s+(-[a-zA-Z]*f|-[a-zA-Z]*r|--force|--recursive)'
    'rm\s+-[a-zA-Z]*r[a-zA-Z]*f'

    # Destructive git operations
    'git\s+reset\s+--hard'
    'git\s+clean\s+(-[a-zA-Z]*f|--force)'
    'git\s+push\s+(-[a-zA-Z]*f|--force)'
    'git\s+push\s+--force-with-lease'
    'git\s+checkout\s+\.'
    'git\s+restore\s+\.'
    'git\s+branch\s+-D'
)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

extract_command() {
    local input
    input=$(cat)
    echo "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

main() {
    local cmd
    cmd=$(extract_command)

    if [ -z "$cmd" ]; then
        exit 0
    fi

    for pattern in "${DANGEROUS_PATTERNS[@]}"; do
        if echo "$cmd" | grep -qE "$pattern"; then
            echo "[validate-bash] BLOCKED: dangerous command detected." >&2
            echo "[validate-bash] Pattern matched: $pattern" >&2
            echo "[validate-bash] Command: $cmd" >&2
            echo "[validate-bash] If this is intentional, run the command manually in your terminal." >&2
            exit 2
        fi
    done

    exit 0
}

main "$@"
