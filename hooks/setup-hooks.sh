#!/bin/sh
#
# Setup local git hooks for claude-flow development.
#
# Usage:
#   sh hooks/setup-hooks.sh
#
# This creates symlinks from .git/hooks/ to the hooks/ directory,
# so the hooks stay version-controlled and auto-update with pulls.

HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

if [ $? -ne 0 ]; then
    echo "Error: not inside a git repository."
    echo "Usage: run this script from inside the claude-flow repo."
    exit 1
fi

for hook in commit-msg pre-commit; do
    if [ -f "$HOOKS_DIR/$hook" ]; then
        ln -sf "$HOOKS_DIR/$hook" "$GIT_HOOKS_DIR/$hook"
        echo "Installed $hook hook -> $GIT_HOOKS_DIR/$hook"
    else
        echo "Warning: $HOOKS_DIR/$hook not found, skipping."
    fi
done

echo ""
echo "Done. Git hooks installed."
echo "To uninstall, delete the symlinks in $GIT_HOOKS_DIR/"
