#!/bin/bash
# protect-files.sh — PreToolUse hook that warns/blocks edits to protected paths
#
# Usage: Configure as a Claude Code PreToolUse Hook
#   .claude/settings.json:
#   {
#     "hooks": {
#       "PreToolUse": [
#         { "matcher": "Edit",  "command": "bash .claude/hooks/protect-files.sh" },
#         { "matcher": "Write", "command": "bash .claude/hooks/protect-files.sh" }
#       ]
#     }
#   }
#
# How it works:
#   1. Reads the tool input JSON from stdin to extract file_path
#   2. Checks the path against hard-protected and soft-protected pattern lists
#   3. Hard match  -> prints an error to stderr and exits 2 (Claude Code blocks the tool call)
#   4. Soft match  -> prints a warning to stderr and exits 0 (Claude Code allows but sees warning)
#
# Environment provided by Claude Code:
#   CLAUDE_TOOL_NAME — name of the tool being called (Edit, Write, …)
#   stdin            — JSON object with the tool's input parameters

set -euo pipefail

# ---------------------------------------------------------------------------
# CONFIGURATION — replace {placeholder} values for your project
# ---------------------------------------------------------------------------

# Hard-protected: Claude Code is BLOCKED from editing these paths.
# Add patterns that should never be auto-modified (glob-style prefix match).
HARD_PROTECTED=(
    "{protected-config-dir}"     # e.g. "ProjectSettings/"
    "ProjectSettings/"           # Unity project settings — edit in Unity Editor only
    ".env"
    ".env.local"
    ".env.production"
)

# Soft-protected: Claude Code is WARNED but allowed to proceed.
# Add patterns for generated/derived artefacts that are risky to hand-edit.
SOFT_PROTECTED=(
    "{protected-generated-dir}"  # e.g. "build/" or "dist/"
    "Library/"                   # Unity Library cache — never hand-edit
    "Temp/"                      # Unity temp files — never hand-edit
    "Logs/"                      # Unity log output
    "node_modules/"
    "__pycache__/"
    "*.lock"
    "*.asset"                    # Root-level .asset files (ScriptableObject singletons, etc.)
)

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

# Extract the value of "file_path" from the JSON on stdin.
# Uses only sed/awk (standard POSIX tools) — no jq required.
extract_file_path() {
    # Capture full stdin first so we can read it once
    local input
    input=$(cat)

    # Try a simple pattern match: "file_path": "some/path"
    echo "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

# Returns 0 if $1 matches any pattern in the supplied array.
matches_any() {
    local path="$1"
    shift
    local pattern
    for pattern in "$@"; do
        # Skip placeholder entries that were never replaced
        if [[ "$pattern" == "{"*"}" ]]; then
            continue
        fi

        # Glob / prefix match
        case "$path" in
            $pattern*) return 0 ;;
        esac

        # Also match if path contains the pattern anywhere (for mid-path dirs)
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
        # No file_path in input — nothing to check
        exit 0
    fi

    # Hard-protected check
    if matches_any "$file_path" "${HARD_PROTECTED[@]}"; then
        echo "[protect-files] BLOCKED: '${file_path}' matches a hard-protected pattern." >&2
        echo "[protect-files] If this edit is intentional, edit the file manually." >&2
        exit 2
    fi

    # Soft-protected check
    if matches_any "$file_path" "${SOFT_PROTECTED[@]}"; then
        echo "[protect-files] WARNING: '${file_path}' is in a soft-protected (generated) path." >&2
        echo "[protect-files] Proceeding, but verify this edit is intentional." >&2
        exit 0
    fi

    exit 0
}

main "$@"
