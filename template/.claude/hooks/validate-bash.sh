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
#
# How it works:
#   1. Reads the tool input JSON from stdin to extract the command
#   2. Checks the command against a list of dangerous patterns
#   3. Match -> prints an error to stderr and exits 2 (Claude Code blocks the tool call)
#
# Environment provided by Claude Code:
#   CLAUDE_TOOL_NAME — name of the tool being called (Bash)
#   stdin            — JSON object with the tool's input parameters

set -euo pipefail

# ---------------------------------------------------------------------------
# DANGEROUS COMMAND PATTERNS
# ---------------------------------------------------------------------------

# Each pattern is a regex checked against the command string.
# Add project-specific dangerous patterns as needed.
DANGEROUS_PATTERNS=(
    # Destructive file operations
    'rm\s+(-[a-zA-Z]*f|-[a-zA-Z]*r|--force|--recursive)' # rm -rf, rm -f, rm --force
    'rm\s+-[a-zA-Z]*r[a-zA-Z]*f'                          # rm -rf (flag order variant)

    # Destructive git operations
    'git\s+reset\s+--hard'          # destroys uncommitted work
    'git\s+clean\s+(-[a-zA-Z]*f|--force)' # deletes untracked files
    'git\s+push\s+(-[a-zA-Z]*f|--force)'  # rewrites remote history
    'git\s+push\s+--force-with-lease'      # still rewrites history
    'git\s+checkout\s+\.'           # discards all unstaged changes
    'git\s+restore\s+\.'            # discards all unstaged changes
    'git\s+branch\s+-D'             # force-delete branch without merge check

    # Dangerous system commands
    '{dangerous-command-pattern}'    # project-specific (placeholder)
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
        # Skip placeholder entries that were never replaced
        if [[ "$pattern" == "{"*"}" ]]; then
            continue
        fi

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
