#!/usr/bin/env bash
# Unity asset operations CLI wrapper (batch mode).
# Usage: bash .claude/scripts/unity-ops.sh <command> [json-file|-] [--overwrite] [--timeout N]
#
# Commands:
#   create-scene <json>     Create a new scene from JSON definition
#   edit-scene <json>       Edit an existing scene
#   list-scenes             List all scenes in the project
#   create-prefab <json>    Create a new prefab from JSON definition
#   list-prefabs [path]     List prefabs (optionally filtered by path)
#   create-material <json>  Create a new material from JSON definition
#   create-folder <path>    Create an asset folder (recursive)
#   list-assets [--type T] [--path P]  List assets with optional filters
#
# JSON can be a file path or '-' for stdin.
#
# {placeholder} values are replaced by /init-project. Customize after init if needed.
# Replace {unity_ops_runner_class} with your C# batch mode entry point,
# e.g. "MyGame.Tools.BatchMode.UnityOpsRunner"
#
# Exit codes: 0=success, 1=operation failed, 2=timeout, 3=infrastructure error

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/unity-env.sh"

log() { echo "[unity-ops] $*"; }

# --- Parse arguments ---
COMMAND="${1:-}"
shift || true

if [[ -z "$COMMAND" ]]; then
    echo "Usage: bash .claude/scripts/unity-ops.sh <command> [json-file|-] [--overwrite] [--timeout N]"
    echo ""
    echo "Commands: create-scene, edit-scene, list-scenes,"
    echo "          create-prefab, list-prefabs,"
    echo "          create-material, create-folder, list-assets"
    exit 3
fi

JSON_FILE=""
OVERWRITE=false
TIMEOUT="$OPS_TIMEOUT"
EXTRA_PATH=""
ASSET_TYPE=""
ASSET_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --overwrite) OVERWRITE=true; shift ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --type) ASSET_TYPE="$2"; shift 2 ;;
        --path) ASSET_PATH="$2"; shift 2 ;;
        -) JSON_FILE="-"; shift ;;
        *)
            if [[ -z "$JSON_FILE" && -z "$EXTRA_PATH" ]]; then
                # Could be a json file or a path argument
                if [[ -f "$1" ]]; then
                    JSON_FILE="$1"
                else
                    EXTRA_PATH="$1"
                fi
            fi
            shift
            ;;
    esac
done

# --- Build JSON command envelope ---
TIMESTAMP=$(date +%Y%m%d%H%M%S)
CMD_ID="ops-${TIMESTAMP}"
CMD_FILE="$COMMANDS_DIR/pending.json"

build_envelope() {
    local params="$1"
    cat <<ENDJSON
{
  "id": "${CMD_ID}",
  "command": "${COMMAND}",
  "overwrite": ${OVERWRITE},
  "params": ${params}
}
ENDJSON
}

case "$COMMAND" in
    create-scene|edit-scene|create-prefab|create-material)
        # These commands require JSON input
        if [[ "$JSON_FILE" == "-" ]]; then
            PARAMS=$(cat)
        elif [[ -n "$JSON_FILE" ]]; then
            PARAMS=$(cat "$JSON_FILE")
        else
            log "ERROR: Command '$COMMAND' requires a JSON file or '-' for stdin"
            exit 3
        fi
        build_envelope "$PARAMS" > "$CMD_FILE"
        ;;

    list-scenes)
        build_envelope '{}' > "$CMD_FILE"
        ;;

    list-prefabs)
        if [[ -n "$EXTRA_PATH" ]]; then
            # Use python for safe JSON construction (stdlib only)
            PARAMS=$(python -c "import json; print(json.dumps({'path': '$EXTRA_PATH'}))")
            build_envelope "$PARAMS" > "$CMD_FILE"
        else
            build_envelope '{}' > "$CMD_FILE"
        fi
        ;;

    create-folder)
        if [[ -z "$EXTRA_PATH" ]]; then
            log "ERROR: create-folder requires a path argument"
            exit 3
        fi
        PARAMS=$(python -c "import json; print(json.dumps({'path': '$EXTRA_PATH'}))")
        build_envelope "$PARAMS" > "$CMD_FILE"
        ;;

    list-assets)
        PARAMS=$(python -c "
import json
d = {}
if '$ASSET_TYPE': d['type'] = '$ASSET_TYPE'
if '$ASSET_PATH': d['path'] = '$ASSET_PATH'
print(json.dumps(d))
")
        build_envelope "$PARAMS" > "$CMD_FILE"
        ;;

    *)
        log "ERROR: Unknown command: $COMMAND"
        exit 3
        ;;
esac

log "Command: $COMMAND (id=$CMD_ID, overwrite=$OVERWRITE)"

# --- Check Editor ---
if ! bash "$SCRIPT_DIR/unity-check-editor.sh"; then
    log "ERROR: Could not close Editor. Aborting."
    exit 3
fi

# --- Run Unity ---
log "Running Unity batch mode... (timeout=${TIMEOUT}s)"
START_TIME=$SECONDS

UNITY_EXIT=0
timeout "$TIMEOUT" "$UNITY_EXE" \
    -batchmode -nographics \
    -projectPath "$PROJECT_PATH" \
    -logFile "$OPS_LOG" \
    -executeMethod "{unity_ops_runner_class}.Run" \
    -- --ops-command "$CMD_FILE" \
    2>&1 || UNITY_EXIT=$?

DURATION=$(( SECONDS - START_TIME ))

# --- Read result ---
RESULT_FILE="$RESULTS_DIR/unity-ops.json"

case $UNITY_EXIT in
    0)
        log "Operation SUCCESS (${DURATION}s)"
        ;;
    124)
        log "Operation TIMEOUT after ${TIMEOUT}s"
        if [[ -f "$RESULT_FILE" ]]; then
            cat "$RESULT_FILE"
        fi
        exit 2
        ;;
    *)
        log "Operation FAILED (exit code $UNITY_EXIT, ${DURATION}s)"
        ;;
esac

if [[ -f "$RESULT_FILE" ]]; then
    cat "$RESULT_FILE"
    echo ""  # Ensure newline
else
    log "WARNING: Result file not found at $RESULT_FILE"
    # Try to extract useful info from log
    if [[ -f "$OPS_LOG" ]]; then
        grep -E "\[UnityOps\]" "$OPS_LOG" 2>/dev/null || true
    fi
fi

# Return appropriate exit code
if [[ $UNITY_EXIT -ne 0 ]]; then
    exit 1
fi
exit 0
