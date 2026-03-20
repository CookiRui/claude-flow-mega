#!/bin/bash
# protect-files.sh — PreToolUse hook that warns/blocks edits to protected paths
#
# Usage: Configure as a Claude Code PreToolUse Hook
#   .claude/settings.json:
#   {
#     "hooks": {
#       "PreToolUse": [
#         { "matcher": "Edit|Write", "command": "bash .claude/hooks/protect-files.sh" }
#       ]
#     }
#   }

set -euo pipefail

# ---------------------------------------------------------------------------
# CONFIGURATION — claude-flow project-specific paths
# ---------------------------------------------------------------------------

# Hard-protected: Claude Code is BLOCKED from editing these paths.
HARD_PROTECTED=(
    ".env"
    ".env.local"
    ".env.production"
    "package-lock.json"
)

# Soft-protected: Claude Code is WARNED but allowed to proceed.
SOFT_PROTECTED=(
    "node_modules/"
    "__pycache__/"
    ".pytest_cache/"
    ".ruff_cache/"
    ".repo-map.json"
    ".repo-map.md"
)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

extract_file_path() {
    local input
    input=$(cat)
    echo "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

matches_any() {
    local path="$1"
    shift
    local pattern
    for pattern in "$@"; do
        case "$path" in
            $pattern*) return 0 ;;
        esac
        case "$path" in
            */$pattern*) return 0 ;;
        esac
    done
    return 1
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

main() {
    local file_path
    file_path=$(extract_file_path)

    if [ -z "$file_path" ]; then
        exit 0
    fi

    if matches_any "$file_path" "${HARD_PROTECTED[@]}"; then
        echo "[protect-files] BLOCKED: '${file_path}' matches a hard-protected pattern." >&2
        echo "[protect-files] If this edit is intentional, edit the file manually." >&2
        exit 2
    fi

    if matches_any "$file_path" "${SOFT_PROTECTED[@]}"; then
        echo "[protect-files] WARNING: '${file_path}' is in a soft-protected (generated) path." >&2
        echo "[protect-files] Proceeding, but verify this edit is intentional." >&2
        exit 0
    fi

    exit 0
}

main "$@"
