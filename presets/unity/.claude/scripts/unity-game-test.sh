#!/usr/bin/env bash
# Unity batch mode PlayMode game test runner.
# Usage:
#   bash .claude/scripts/unity-game-test.sh smoke --scene Assets/Scenes/MyScene.unity
#   bash .claude/scripts/unity-game-test.sh run-test path/to/test.json --scene Assets/Scenes/X.unity [--var key=value]
#   bash .claude/scripts/unity-game-test.sh run-test - --scene Assets/Scenes/X.unity  (stdin JSON)
#
# {placeholder} values are replaced by /init-project. Customize after init if needed.
# Exit codes: 0=passed, 1=failed, 2=timeout, 3=infrastructure error

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/unity-env.sh"

log() { echo "[monitor] $*"; }

MODE="${1:-}"

show_usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  smoke              Smoke test (enter PlayMode, verify scene loads)"
    echo "  run-test <file|->  Execute a JSON test case file (- for stdin)"
    echo ""
    echo "Options:"
    echo "  --scene <path>     (required for smoke/run-test) Unity scene path"
    echo "  --var key=value    (run-test only) Override test parameters"
}

# ─── Parse arguments for smoke / run-test ────────────────────────────────────
SCENE_PATH=""
TEST_CASE_FILE=""
VAR_ARGS=()

case "$MODE" in
    smoke)
        shift
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --scene) SCENE_PATH="${2:-}"; shift 2 ;;
                *) echo "Unknown argument: $1"; exit 1 ;;
            esac
        done
        ;;
    run-test)
        shift
        TEST_CASE_FILE="${1:-}"
        if [[ -z "$TEST_CASE_FILE" ]]; then
            echo "ERROR: run-test requires a test case file path (or - for stdin)."
            show_usage
            exit 1
        fi
        shift
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --scene) SCENE_PATH="${2:-}"; shift 2 ;;
                --var) VAR_ARGS+=("-var" "${2:-}"); shift 2 ;;
                *) echo "Unknown argument: $1"; exit 1 ;;
            esac
        done
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

# ─── Handle stdin mode for run-test ──────────────────────────────────────────
STDIN_JSON_FILE=""
if [[ "$MODE" == "run-test" && "$TEST_CASE_FILE" == "-" ]]; then
    STDIN_JSON_FILE="$COMMANDS_DIR/stdin_test_$(date +%Y%m%d_%H%M%S).json"
    mkdir -p "$COMMANDS_DIR"
    cat > "$STDIN_JSON_FILE"
    TEST_CASE_FILE="$STDIN_JSON_FILE"
    log "Stdin JSON saved to $STDIN_JSON_FILE"
fi

# ─── Validate test case file exists ──────────────────────────────────────────
if [[ "$MODE" == "run-test" ]]; then
    # Convert relative path to absolute
    if [[ ! "$TEST_CASE_FILE" = /* ]]; then
        TEST_CASE_FILE="$(cd "$REPO_ROOT" && pwd)/$TEST_CASE_FILE"
    fi
    if [[ ! -f "$TEST_CASE_FILE" ]]; then
        echo "ERROR: Test case file not found: $TEST_CASE_FILE"
        exit 3
    fi

    # If no --scene, try to extract from JSON
    if [[ -z "$SCENE_PATH" ]]; then
        SCENE_PATH=$(python -c "import json,sys; d=json.load(open(sys.argv[1],'r',encoding='utf-8')); print(d.get('scene',''))" "$TEST_CASE_FILE" 2>/dev/null || true)
    fi
fi

# ─── Validate scene ─────────────────────────────────────────────────────────
if [[ -z "$SCENE_PATH" ]]; then
    echo "ERROR: Missing required --scene argument (or 'scene' field in JSON)."
    echo "Usage: bash .claude/scripts/unity-game-test.sh $MODE --scene Assets/Scenes/<YourScene>.unity"
    exit 1
fi

# ─── Pre-launch checks ──────────────────────────────────────────────────────
bash "$SCRIPT_DIR/unity-check-editor.sh"

mkdir -p "$RESULTS_DIR"
rm -f "$RESULTS_DIR"/*.json 2>/dev/null || true
rm -f "$PROGRESS_FILE" 2>/dev/null || true

# ─── Build Unity arguments ──────────────────────────────────────────────────
# Configure the executeMethod for your project's PlayMode runner.
# Replace {batch_playmode_runner_class} with your C# class path,
# e.g. "MyGame.Tools.BatchMode.BatchPlayModeRunner"

if [[ "$MODE" == "smoke" ]]; then
    EXECUTE_METHOD="{batch_playmode_runner_class}.Run"
    UNITY_ARGS=(
        -batchmode
        -projectPath "$PROJECT_PATH"
        -executeMethod "$EXECUTE_METHOD"
        -logFile "$TEST_LOG"
        -scene "$SCENE_PATH"
    )
elif [[ "$MODE" == "run-test" ]]; then
    EXECUTE_METHOD="{batch_playmode_runner_class}.RunTest"
    UNITY_ARGS=(
        -batchmode
        -projectPath "$PROJECT_PATH"
        -executeMethod "$EXECUTE_METHOD"
        -logFile "$TEST_LOG"
        -scene "$SCENE_PATH"
        -testCase "$TEST_CASE_FILE"
    )
    # Append -var arguments
    for arg in "${VAR_ARGS[@]+"${VAR_ARGS[@]}"}"; do
        UNITY_ARGS+=("$arg")
    done
fi

# ─── Launch Unity in background ─────────────────────────────────────────────
"$UNITY_EXE" "${UNITY_ARGS[@]}" &
BASH_PID=$!
sleep 3

# Get the actual Windows PID for reliable force-kill
WIN_PID=$(powershell.exe -NoProfile -Command \
    "(Get-Process -Name Unity -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1).Id" 2>/dev/null | tr -d '\r')

log "Unity launched (PID ${WIN_PID:-unknown}, bash PID $BASH_PID)"
log "Mode: $MODE, Method: $EXECUTE_METHOD"

START_TIME=$SECONDS
PHASE="launching"
LAST_MILESTONE="Unity process started"
RESULT_FOUND=false
COMPILE_DETECTED=false
LOG_OFFSET=0
RESULT_TIME=0

# Write heartbeat file
write_progress() {
    cat > "$PROGRESS_FILE" <<EOF
PHASE=$PHASE
ELAPSED=$(( SECONDS - START_TIME ))
LAST_MILESTONE=$LAST_MILESTONE
RESULT_FOUND=$RESULT_FOUND
COMPILE_DETECTED=$COMPILE_DETECTED
UNITY_PID=${WIN_PID:-unknown}
EOF
}

# Check if Unity bash wrapper is still alive
is_unity_alive() {
    kill -0 "$BASH_PID" 2>/dev/null
}

# Phase order (numeric rank) for monotonic advancement
phase_rank() {
    case "$1" in
        launching)         echo 0 ;;
        domain_reload)     echo 1 ;;
        execute_method)    echo 2 ;;
        playmode_entering) echo 3 ;;
        test_running)      echo 4 ;;
        ready)             echo 5 ;;
        exiting)           echo 6 ;;
        *)                 echo 99 ;;
    esac
}

CURRENT_RANK=0

# Advance PHASE only if new phase is higher rank
try_advance() {
    local new_phase="$1" new_milestone="$2"
    local new_rank
    new_rank=$(phase_rank "$new_phase")
    if (( new_rank > CURRENT_RANK )); then
        PHASE="$new_phase"
        LAST_MILESTONE="$new_milestone"
        CURRENT_RANK=$new_rank
        log "$(( SECONDS - START_TIME ))s: $PHASE — $LAST_MILESTONE"
    fi
}

# Scan new log lines for milestones
# Customize the grep patterns below to match your project's log output.
scan_log() {
    [[ -f "$TEST_LOG" ]] || return 0
    local file_lines
    file_lines=$(wc -l < "$TEST_LOG" 2>/dev/null || echo 0)
    file_lines=$(( file_lines + 0 ))  # ensure numeric
    if (( file_lines <= LOG_OFFSET )); then
        return 0
    fi

    local new_lines
    new_lines=$(tail -n +"$(( LOG_OFFSET + 1 ))" "$TEST_LOG" 2>/dev/null || true)
    LOG_OFFSET=$file_lines

    # Check for compilation (first-time build detection)
    if [[ "$COMPILE_DETECTED" == "false" ]] && echo "$new_lines" | grep -qE "Compilation started|ExitCode: 0 Duration:"; then
        COMPILE_DETECTED=true
    fi

    # Milestone matching — PHASE only advances forward, never regresses
    # Adjust these patterns to match your project's batch mode runner output.
    if echo "$new_lines" | grep -q "Domain Reload Profiling"; then
        try_advance "domain_reload" "Domain Reload Profiling"
    fi
    if echo "$new_lines" | grep -qE "\[BatchPlayModeRunner\].*Starting|executeMethod.*Starting"; then
        try_advance "execute_method" "BatchPlayModeRunner starting"
    fi
    if echo "$new_lines" | grep -q "Starting game-ready poll"; then
        try_advance "playmode_entering" "Starting game-ready poll"
    fi
    if echo "$new_lines" | grep -qE "\[Test\]|\[AutoTest\]"; then
        try_advance "test_running" "Test executing"
    fi
    if echo "$new_lines" | grep -q "PlayMode ready"; then
        try_advance "ready" "PlayMode ready"
    fi
    if echo "$new_lines" | grep -q "Smoke test passed"; then
        try_advance "ready" "Smoke test passed"
    fi
    if echo "$new_lines" | grep -qE "Test completed|AutoTest completed"; then
        try_advance "ready" "Test completed"
    fi
    if echo "$new_lines" | grep -qE "exiting with code|Exiting batchmode"; then
        try_advance "exiting" "Unity exiting"
    fi
    return 0
}

# ─── Monitor loop (every 2 seconds) ─────────────────────────────────────────
while true; do
    sleep 2
    ELAPSED=$(( SECONDS - START_TIME ))

    # 1. Check for result JSON
    if [[ "$RESULT_FOUND" == "false" ]]; then
        RESULT_FILE=$(ls -t "$RESULTS_DIR"/*.json 2>/dev/null | head -1 || true)
        if [[ -n "${RESULT_FILE:-}" ]]; then
            RESULT_FOUND=true
            RESULT_TIME=$ELAPSED
            PHASE="completed"
            LAST_MILESTONE="Result JSON found"
            log "${ELAPSED}s: Result found!"
            log "--- Result ---"
            cat "$RESULT_FILE"
            log "--- End ---"
            write_progress
        fi
    fi

    # 2. If result found, wait for Unity graceful shutdown
    if [[ "$RESULT_FOUND" == "true" ]]; then
        if ! is_unity_alive; then
            log "Unity exited normally. Done in ${ELAPSED}s"
            write_progress
            if grep -q '"status"[[:space:]]*:[[:space:]]*"passed"' "$RESULT_FILE" 2>/dev/null; then
                exit 0
            else
                exit 1
            fi
        fi
        SHUTDOWN_WAIT=$(( ELAPSED - RESULT_TIME ))
        if (( SHUTDOWN_WAIT >= GRACEFUL_SHUTDOWN_TIMEOUT )); then
            PHASE="shutdown_timeout"
            LAST_MILESTONE="Unity still running ${SHUTDOWN_WAIT}s after result"
            log "${ELAPSED}s: shutdown_timeout — Unity did not exit within ${GRACEFUL_SHUTDOWN_TIMEOUT}s after result."
            log "Result already captured. Exiting script (Unity still running)."
            write_progress
            if grep -q '"status"[[:space:]]*:[[:space:]]*"passed"' "$RESULT_FILE" 2>/dev/null; then
                exit 0
            else
                exit 1
            fi
        fi
        write_progress
        continue
    fi

    # 3. Check Unity process alive (no result yet)
    if ! is_unity_alive; then
        PHASE="exited"
        LAST_MILESTONE="Unity exited without result (code: $(wait "$BASH_PID" 2>/dev/null; echo $?))"
        log "${ELAPSED}s: Unity exited without producing result JSON!"
        write_progress
        exit 1
    fi

    # 4. Check overall timeout
    if (( ELAPSED >= TEST_TIMEOUT )); then
        PHASE="timeout"
        LAST_MILESTONE="Timeout after ${TEST_TIMEOUT}s"
        log "${ELAPSED}s: TIMEOUT — killing Unity..."
        if [[ -n "${WIN_PID:-}" ]]; then
            powershell.exe -NoProfile -Command \
                "Stop-Process -Id $WIN_PID -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
        fi
        sleep 2
        rm -f "$PROJECT_PATH/Temp/UnityLockfile" 2>/dev/null || true
        write_progress
        exit 2
    fi

    # 5. Scan log for milestones
    scan_log

    # 6. Write heartbeat
    write_progress
done
