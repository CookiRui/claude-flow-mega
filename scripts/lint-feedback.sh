#!/bin/bash
# lint-feedback.sh — Bidirectional feedback: structured error output on lint failure
#
# Usage: Configure as a Claude Code Hook
#   .claude/settings.json:
#   {
#     "hooks": {
#       "PostToolUse": [
#         { "matcher": "Edit", "command": "bash scripts/lint-feedback.sh" },
#         { "matcher": "Write", "command": "bash scripts/lint-feedback.sh" }
#       ]
#     }
#   }
#
# How it works:
#   1. Detects project type (Node/Python/C#/Go/Rust)
#   2. Runs lint on changed files
#   3. If lint fails, outputs errors to stderr
#   4. Claude Code reads stderr and auto-fixes (bidirectional feedback loop)

set -euo pipefail

# Get recently changed files via git diff
get_changed_files() {
    git diff --name-only HEAD 2>/dev/null || true
    git diff --name-only --cached 2>/dev/null || true
}

# Detect and run lint
run_lint() {
    local file="$1"
    local ext="${file##*.}"
    local lint_output=""
    local lint_exit=0

    case "$ext" in
        js|jsx|ts|tsx)
            if command -v npx &> /dev/null && [ -f "package.json" ]; then
                lint_output=$(npx eslint "$file" --no-error-on-unmatched-pattern 2>&1) || lint_exit=$?
            fi
            ;;
        py)
            if command -v ruff &> /dev/null; then
                lint_output=$(ruff check "$file" 2>&1) || lint_exit=$?
            elif command -v flake8 &> /dev/null; then
                lint_output=$(flake8 "$file" 2>&1) || lint_exit=$?
            fi
            ;;
        cs)
            if command -v dotnet &> /dev/null; then
                lint_output=$(dotnet format --verify-no-changes --include "$file" 2>&1) || lint_exit=$?
            fi
            ;;
        go)
            if command -v golangci-lint &> /dev/null; then
                lint_output=$(golangci-lint run "$file" 2>&1) || lint_exit=$?
            elif command -v go &> /dev/null; then
                lint_output=$(go vet "./${file%/*}/..." 2>&1) || lint_exit=$?
            fi
            ;;
        rs)
            if command -v cargo &> /dev/null; then
                lint_output=$(cargo clippy --message-format=short 2>&1) || lint_exit=$?
            fi
            ;;
    esac

    if [ $lint_exit -ne 0 ] && [ -n "$lint_output" ]; then
        echo "LINT_ERROR in $file:" >&2
        echo "$lint_output" >&2
        return 1
    fi

    return 0
}

# Main flow
main() {
    local files
    files=$(get_changed_files)

    if [ -z "$files" ]; then
        exit 0
    fi

    local has_error=0

    while IFS= read -r file; do
        if [ -f "$file" ]; then
            run_lint "$file" || has_error=1
        fi
    done <<< "$files"

    exit $has_error
}

main "$@"
