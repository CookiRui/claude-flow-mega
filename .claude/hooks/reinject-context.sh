#!/bin/bash
# reinject-context.sh — SessionStart hook that reinjects key context after compaction

set -euo pipefail

CONSTITUTION_FILE=".claude/constitution.md"
WIP_FILE=".claude-flow/wip.md"

main() {
    echo "========================================================"
    echo "  Context Reinjection — post-compaction restore"
    echo "========================================================"
    echo ""

    if [ -f "$CONSTITUTION_FILE" ]; then
        echo "--- [constitution: $CONSTITUTION_FILE] ---"
        cat "$CONSTITUTION_FILE"
        echo ""
    else
        echo "[reinject-context] WARNING: $CONSTITUTION_FILE not found — skipping." >&2
    fi

    if [ -f "$WIP_FILE" ]; then
        echo "--- [wip: $WIP_FILE] ---"
        cat "$WIP_FILE"
        echo ""
    fi

    echo "========================================================"
    echo "  Context reinjected. Resume work from the WIP above."
    echo "========================================================"
}

main "$@"
