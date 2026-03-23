#!/usr/bin/env bash
# Unity Editor detection and graceful shutdown.
# Exit codes: 0 = no Editor running / successfully closed, 1 = failed to close
#
# Uses PowerShell for process detection — tasklist.exe /FI is unreliable
# in MSYS2/Git Bash on some Windows versions.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/unity-env.sh"

LOCKFILE="$PROJECT_PATH/Temp/UnityLockfile"

log() { echo "[unity-editor] $*"; }

# Check if a PID is alive via PowerShell (reliable on Windows)
is_pid_alive() {
    powershell.exe -NoProfile -Command \
        "if (Get-Process -Id $1 -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" 2>/dev/null
}

# Check if any Unity.exe process is running
is_any_unity_running() {
    powershell.exe -NoProfile -Command \
        "if (Get-Process -Name Unity -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" 2>/dev/null
}

# Clean stale lockfile if no Unity process is running
cleanup_stale_lock() {
    if [[ -f "$LOCKFILE" ]]; then
        if ! is_any_unity_running; then
            log "Removing stale lockfile (no Unity process found)."
            rm -f "$LOCKFILE" 2>/dev/null || true
        fi
    fi
}

# Check if EditorInstance.json exists
if [[ ! -f "$EDITOR_INSTANCE" ]]; then
    cleanup_stale_lock
    log "No EditorInstance.json found — Editor not running."
    exit 0
fi

# Read process_id from JSON (lightweight parsing, no jq dependency)
PID=$(grep -o '"process_id"[[:space:]]*:[[:space:]]*[0-9]*' "$EDITOR_INSTANCE" | grep -o '[0-9]*$')

if [[ -z "$PID" ]]; then
    cleanup_stale_lock
    log "EditorInstance.json exists but no valid PID found — treating as stale lock."
    exit 0
fi

log "Found Editor PID: $PID"

# Check if process is actually alive
if ! is_pid_alive "$PID"; then
    cleanup_stale_lock
    log "PID $PID is not running — stale lock file, safe to proceed."
    exit 0
fi

log "Editor is running (PID $PID). Attempting graceful shutdown..."

# Step 1: Try CloseMainWindow (graceful)
powershell.exe -NoProfile -Command \
    "try { (Get-Process -Id $PID).CloseMainWindow() | Out-Null } catch { }" 2>/dev/null || true

# Step 2: Poll for exit
ELAPSED=0
POLL_INTERVAL=2
while (( ELAPSED < SHUTDOWN_TIMEOUT )); do
    sleep $POLL_INTERVAL
    ELAPSED=$(( ELAPSED + POLL_INTERVAL ))

    if ! is_pid_alive "$PID"; then
        cleanup_stale_lock
        log "Editor closed gracefully (${ELAPSED}s)."
        exit 0
    fi
    log "Waiting... (${ELAPSED}s / ${SHUTDOWN_TIMEOUT}s)"
done

# Step 3: Forced stop via PowerShell
log "Graceful shutdown timed out. Force-stopping..."
powershell.exe -NoProfile -Command \
    "Stop-Process -Id $PID -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
sleep 3

if ! is_pid_alive "$PID"; then
    cleanup_stale_lock
    log "Editor killed."
    exit 0
fi

log "ERROR: Failed to close Editor (PID $PID)."
exit 1
