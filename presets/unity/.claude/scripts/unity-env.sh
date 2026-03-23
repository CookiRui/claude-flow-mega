#!/usr/bin/env bash
# Unity batch mode CLI - shared constants
# All other scripts source this file for common paths and timeouts.
#
# {placeholder} values are replaced by /init-project. Customize after init if needed.

# Path to Unity Editor executable
# Example: "C:/Program Files/Unity/Hub/Editor/2022.3.20f1/Editor/Unity.exe"
UNITY_EXE="{unity_editor_path}"

# Auto-detect repo root (supports CI runner and local development)
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || echo "{project_root}")}"

# Path to the Unity project directory (relative to repo root)
# If your Unity project IS the repo root, use "$REPO_ROOT" directly.
PROJECT_PATH="${REPO_ROOT}/{unity_project_subdir}"

EDITOR_INSTANCE="$PROJECT_PATH/Library/EditorInstance.json"
LOG_DIR="${REPO_ROOT}/.claude/logs"
COMPILE_LOG="$LOG_DIR/compile.log"
TEST_LOG="$LOG_DIR/test.log"
COMPILE_TIMEOUT=300   # 5 minutes
TEST_TIMEOUT=600      # 10 minutes
SHUTDOWN_TIMEOUT=30   # Editor shutdown wait
GRACEFUL_SHUTDOWN_TIMEOUT=120  # Wait for Unity to exit after result found
PROGRESS_FILE="$LOG_DIR/test-progress.txt"
BATCH_MODE_DIR="${REPO_ROOT}/.claude/batch-mode"
RESULTS_DIR="$BATCH_MODE_DIR/results"
COMMANDS_DIR="$BATCH_MODE_DIR/commands"
OPS_LOG="$LOG_DIR/unity-ops.log"
OPS_TIMEOUT=300  # 5 minutes for asset operations

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$RESULTS_DIR"
mkdir -p "$COMMANDS_DIR"
