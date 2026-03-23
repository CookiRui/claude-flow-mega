#!/usr/bin/env bash
# Parse Unity compile log and extract errors/warnings as JSON.
# Usage: bash .claude/scripts/unity-parse-compile-log.sh <log-file>
# Output: JSON to stdout
#
# Unity on Windows uses backslash paths (Assets\Scripts\...) — we normalize to forward slashes.
# Unity may log the same error multiple times — we deduplicate by file+line+col+code.
# Pure bash, no external dependencies.

set -euo pipefail

LOG_FILE="${1:-}"
if [[ -z "$LOG_FILE" || ! -f "$LOG_FILE" ]]; then
    echo '{"success":false,"errors":[],"warnings":[],"errorCount":0,"warningCount":0,"parseError":"Log file not found"}'
    exit 0
fi

ERRORS=""
WARNINGS=""
ERROR_COUNT=0
WARNING_COUNT=0

# Associative arrays for deduplication
declare -A SEEN_ERRORS
declare -A SEEN_WARNINGS

# Roslyn error format (after backslash normalization):
#   Assets/path/File.cs(line,col): error CSxxxx: message
PATTERN='Assets/[^(]+\([0-9]+,[0-9]+\): (error|warning) CS[0-9]+:'

while IFS= read -r line; do
    # Normalize backslashes to forward slashes
    line="${line//\\//}"

    # Match error lines
    if echo "$line" | grep -qE "^${PATTERN}"; then
        # Extract severity (error or warning)
        if echo "$line" | grep -qE '^Assets/[^(]+\([0-9]+,[0-9]+\): error CS[0-9]+:'; then
            SEVERITY="error"
        else
            SEVERITY="warning"
        fi

        FILE=$(echo "$line" | sed -E "s/^(Assets\/[^(]+)\([0-9]+,[0-9]+\): ${SEVERITY} CS[0-9]+:.*/\1/")
        LINE_NUM=$(echo "$line" | sed -E "s/^Assets\/[^(]+\(([0-9]+),[0-9]+\): ${SEVERITY} CS[0-9]+:.*/\1/")
        COL_NUM=$(echo "$line" | sed -E "s/^Assets\/[^(]+\([0-9]+,([0-9]+)\): ${SEVERITY} CS[0-9]+:.*/\1/")
        CODE=$(echo "$line" | sed -E "s/^Assets\/[^(]+\([0-9]+,[0-9]+\): ${SEVERITY} (CS[0-9]+):.*/\1/")
        MSG=$(echo "$line" | sed -E "s/^Assets\/[^(]+\([0-9]+,[0-9]+\): ${SEVERITY} CS[0-9]+: (.*)/\1/")
        # Escape JSON special chars in message
        MSG=$(echo "$MSG" | sed 's/\\/\\\\/g; s/"/\\"/g')

        # Dedup key
        DEDUP_KEY="${FILE}:${LINE_NUM}:${COL_NUM}:${CODE}"

        if [[ "$SEVERITY" == "error" ]]; then
            if [[ -z "${SEEN_ERRORS[$DEDUP_KEY]:-}" ]]; then
                SEEN_ERRORS[$DEDUP_KEY]=1
                if [[ $ERROR_COUNT -gt 0 ]]; then ERRORS="$ERRORS,"; fi
                ERRORS="$ERRORS{\"file\":\"$FILE\",\"line\":$LINE_NUM,\"col\":$COL_NUM,\"code\":\"$CODE\",\"message\":\"$MSG\"}"
                ERROR_COUNT=$(( ERROR_COUNT + 1 ))
            fi
        else
            if [[ -z "${SEEN_WARNINGS[$DEDUP_KEY]:-}" ]]; then
                SEEN_WARNINGS[$DEDUP_KEY]=1
                if [[ $WARNING_COUNT -gt 0 ]]; then WARNINGS="$WARNINGS,"; fi
                WARNINGS="$WARNINGS{\"file\":\"$FILE\",\"line\":$LINE_NUM,\"col\":$COL_NUM,\"code\":\"$CODE\",\"message\":\"$MSG\"}"
                WARNING_COUNT=$(( WARNING_COUNT + 1 ))
            fi
        fi
    fi
done < "$LOG_FILE"

SUCCESS="true"
if [[ $ERROR_COUNT -gt 0 ]]; then
    SUCCESS="false"
fi

echo "{\"success\":$SUCCESS,\"errors\":[$ERRORS],\"warnings\":[$WARNINGS],\"errorCount\":$ERROR_COUNT,\"warningCount\":$WARNING_COUNT}"
