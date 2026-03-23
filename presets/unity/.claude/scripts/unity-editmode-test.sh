#!/usr/bin/env bash
# Unity EditMode unit test runner (NUnit).
# Usage: bash .claude/scripts/unity-editmode-test.sh [--filter <pattern>]
# Exit codes: 0=all passed, 1=test failures, 2=timeout, 3=error

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/unity-env.sh"

FILTER=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --filter)
            FILTER="${2:-}"
            if [[ -z "$FILTER" ]]; then
                echo "ERROR: --filter requires a pattern argument"
                exit 3
            fi
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--filter <pattern>]"
            exit 3
            ;;
    esac
done

log() { echo "[editmode] $*"; }

# Step 1: Close existing Editor
bash "$SCRIPT_DIR/unity-check-editor.sh"
if [[ $? -ne 0 ]]; then
    log "ERROR: Could not close Editor. Aborting."
    exit 3
fi

# Step 2: Setup paths
TEST_LOG_FILE="$LOG_DIR/editmode-test.log"
RESULTS_XML="$RESULTS_DIR/editmode-results.xml"
rm -f "$RESULTS_XML"

# Step 3: Build Unity arguments
UNITY_ARGS=(
    -batchmode -nographics
    -projectPath "$PROJECT_PATH"
    -runTests -testPlatform EditMode
    -testResults "$RESULTS_XML"
    -logFile "$TEST_LOG_FILE"
)
if [[ -n "$FILTER" ]]; then
    UNITY_ARGS+=(-testFilter "$FILTER")
    log "Filter: $FILTER"
fi

# Step 4: Run tests
log "Running EditMode tests... (timeout=${TEST_TIMEOUT}s)"
START_TIME=$SECONDS

UNITY_EXIT=0
timeout "$TEST_TIMEOUT" "$UNITY_EXE" "${UNITY_ARGS[@]}" 2>&1 || UNITY_EXIT=$?

DURATION=$(( SECONDS - START_TIME ))

# Step 5: Interpret exit code
SCRIPT_EXIT=0
case $UNITY_EXIT in
    0)
        log "All tests PASSED (${DURATION}s)"
        SCRIPT_EXIT=0
        ;;
    2)
        log "Some tests FAILED (${DURATION}s)"
        SCRIPT_EXIT=1
        ;;
    124)
        log "TIMEOUT after ${TEST_TIMEOUT}s"
        SCRIPT_EXIT=2
        ;;
    *)
        log "ERROR: Unity exited with code $UNITY_EXIT (${DURATION}s)"
        SCRIPT_EXIT=3
        ;;
esac

# Step 6: Parse results
if [[ -f "$RESULTS_XML" ]]; then
    log "Parsing XML results..."
    python "$SCRIPT_DIR/unity-parse-test-results.py" "$RESULTS_XML"
elif [[ -f "$TEST_LOG_FILE" ]]; then
    log "XML not found, falling back to log parsing..."
    python "$SCRIPT_DIR/unity-parse-test-results.py" --from-log "$TEST_LOG_FILE"
else
    log "WARNING: No results XML or log file found"
    echo '{"source":"error","result":"error","total":0,"passed":0,"failed":0,"skipped":0,"duration":0,"failures":[{"name":"NoOutput","message":"Neither XML nor log file found","stackTrace":""}]}'
fi

exit $SCRIPT_EXIT
