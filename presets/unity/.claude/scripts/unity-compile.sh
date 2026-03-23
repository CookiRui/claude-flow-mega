#!/usr/bin/env bash
# Unity batch mode compilation pipeline.
# Usage: bash .claude/scripts/unity-compile.sh [--skip-editor-check] [--execute-method]
#
# --execute-method: Use -executeMethod {batch_compile_method}
#                   for enhanced reporting (assembly count, DLL count).
#                   Without this flag, uses plain -quit (simpler, no C# dependency).
#
# Exit codes: 0 = success, 1 = compile error, 2 = timeout, 3 = other failure

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/unity-env.sh"

SKIP_EDITOR_CHECK=false
USE_EXECUTE_METHOD=false
for arg in "$@"; do
    case "$arg" in
        --skip-editor-check) SKIP_EDITOR_CHECK=true ;;
        --execute-method) USE_EXECUTE_METHOD=true ;;
        *) echo "Unknown argument: $arg"; exit 3 ;;
    esac
done

log() { echo "[unity] $*"; }

# Step 1: Editor check
if [[ "$SKIP_EDITOR_CHECK" == false ]]; then
    bash "$SCRIPT_DIR/unity-check-editor.sh"
    if [[ $? -ne 0 ]]; then
        log "ERROR: Could not close Editor. Aborting."
        exit 3
    fi
fi

# Step 2: Run Unity batch mode compilation
log "Compiling... (batch mode, timeout=${COMPILE_TIMEOUT}s)"
START_TIME=$SECONDS

UNITY_ARGS=(-batchmode -nographics -projectPath "$PROJECT_PATH" -logFile "$COMPILE_LOG")
if [[ "$USE_EXECUTE_METHOD" == true ]]; then
    # Replace {batch_compile_method} with your C# BatchMode method for enhanced reporting.
    # Example: MyProject.Tools.BatchMode.BatchCompileCheck.Run
    UNITY_ARGS+=(-executeMethod "{batch_compile_method}")
    log "Using -executeMethod for enhanced reporting"
else
    UNITY_ARGS+=(-quit)
fi

UNITY_EXIT=0
timeout "$COMPILE_TIMEOUT" "$UNITY_EXE" "${UNITY_ARGS[@]}" 2>&1 || UNITY_EXIT=$?

DURATION=$(( SECONDS - START_TIME ))

# Step 3: Interpret exit code
case $UNITY_EXIT in
    0)
        log "Compilation SUCCESS (${DURATION}s)"
        ;;
    124)
        log "Compilation TIMEOUT after ${COMPILE_TIMEOUT}s"
        # Still parse log for partial results
        bash "$SCRIPT_DIR/unity-parse-compile-log.sh" "$COMPILE_LOG" 2>/dev/null || true
        exit 2
        ;;
    *)
        log "Compilation FAILED (exit code $UNITY_EXIT, ${DURATION}s)"
        ;;
esac

# Step 4: Parse compile log
if [[ -f "$COMPILE_LOG" ]]; then
    PARSE_OUTPUT=$(bash "$SCRIPT_DIR/unity-parse-compile-log.sh" "$COMPILE_LOG")
    echo "$PARSE_OUTPUT"

    # Extract error count for human-readable summary
    ERROR_COUNT=$(echo "$PARSE_OUTPUT" | grep -o '"errorCount":[0-9]*' | grep -o '[0-9]*' || echo "0")
    WARNING_COUNT=$(echo "$PARSE_OUTPUT" | grep -o '"warningCount":[0-9]*' | grep -o '[0-9]*' || echo "0")
    log "Errors: $ERROR_COUNT | Warnings: $WARNING_COUNT"

    # Extract BatchCompileCheck report if --execute-method was used
    if [[ "$USE_EXECUTE_METHOD" == true ]]; then
        BCR=$(grep -o '\[BatchCompileCheck\] {.*}' "$COMPILE_LOG" | sed 's/\[BatchCompileCheck\] //' || true)
        if [[ -n "$BCR" ]]; then
            log "BatchCompileCheck report: $BCR"
        fi
    fi
else
    log "WARNING: Compile log not found at $COMPILE_LOG"
fi

# Return appropriate exit code
if [[ $UNITY_EXIT -ne 0 ]]; then
    exit 1
fi
exit 0
