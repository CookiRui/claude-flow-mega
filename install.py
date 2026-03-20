#!/usr/bin/env python3
"""
claude-flow installer — One command to set up claude-flow in any project.

Usage:
    python install.py                     # Install to current directory
    python install.py /path/to/project    # Install to specified directory
    python install.py --force             # Overwrite existing files

Remote usage (no clone needed):
    curl -sL https://raw.githubusercontent.com/<owner>/claude-flow/master/install.py | python3 - /path/to/project
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# Files and directories to install
TEMPLATE_ITEMS = [
    "CLAUDE.md",
    "REVIEW.md",
    ".claudeignore",
    ".github/workflows/ci.yml",
    ".claude/constitution.md",
    ".claude/settings.json",
    ".claude/agents/feature-builder.md",
    ".claude/agents/code-reviewer.md",
    ".claude/agents/test-writer.md",
    ".claude/hooks/protect-files.sh",
    ".claude/hooks/reinject-context.sh",
    ".claude/rules/coding-style.md",
    ".claude/rules/git-workflow.md",
    ".claude/rules/security.md",
    ".claude/skills/tdd/SKILL.md",
    ".claude/skills/verification/SKILL.md",
    ".claude/skills/_template/SKILL.md",
    ".claude/skills/_template/references/detail.md",
    ".claude/commands/init-project.md",
    ".claude/commands/feature-plan-creator.md",
    ".claude/commands/bug-fix.md",
    ".claude/commands/deep-task.md",
    ".claude/commands/upgrade.md",
]

SCRIPT_ITEMS = [
    "scripts/persistent-solve.py",
    "scripts/repo-map.py",
    "scripts/lint-feedback.sh",
]


def find_source_dir() -> Path:
    """Find the claude-flow source directory."""
    # When run from the repo
    script_dir = Path(__file__).resolve().parent
    if (script_dir / "template").is_dir():
        return script_dir
    # When piped via curl, look for template in cwd
    cwd = Path.cwd()
    if (cwd / "template").is_dir():
        return cwd
    return script_dir


def install(target: Path, source: Path, force: bool = False):
    """Install claude-flow files to the target directory."""
    template_dir = source / "template"
    scripts_dir = source / "scripts"

    if not template_dir.is_dir():
        print(f"Error: template directory not found at {template_dir}")
        print("Run this script from the claude-flow repository root.")
        sys.exit(1)

    installed = []
    skipped = []

    # Install template files
    for item in TEMPLATE_ITEMS:
        src = template_dir / item
        dst = target / item
        if not src.exists():
            print(f"  Warning: source not found: {src}")
            continue
        if dst.exists() and not force:
            skipped.append(item)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        installed.append(item)

    # Install scripts
    for item in SCRIPT_ITEMS:
        src = source / item
        dst = target / item
        if not src.exists():
            print(f"  Warning: source not found: {src}")
            continue
        if dst.exists() and not force:
            skipped.append(item)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        installed.append(item)

    # Make shell scripts executable
    for item in installed:
        if item.endswith(".sh"):
            p = target / item
            p.chmod(p.stat().st_mode | 0o111)

    # Print results
    print()
    if installed:
        print(f"Installed {len(installed)} files to {target}:")
        for f in installed:
            print(f"  + {f}")
    if skipped:
        print(f"\nSkipped {len(skipped)} existing files (use --force to overwrite):")
        for f in skipped:
            print(f"  ~ {f}")
    if not installed and not skipped:
        print("Nothing to install.")
        return

    print()
    print("Next steps:")
    print(f"  cd {target}")
    print("  claude")
    print("  > /init-project")
    print()
    print("This will auto-analyze your project and replace all template")
    print("placeholders with project-specific configuration.")


def main():
    parser = argparse.ArgumentParser(
        description="Install claude-flow into a project"
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target project directory (default: current directory)",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing files",
    )

    args = parser.parse_args()
    target = Path(args.target).resolve()
    source = find_source_dir()

    if not target.is_dir():
        print(f"Error: target directory does not exist: {target}")
        sys.exit(1)

    print(f"Installing claude-flow to: {target}")
    install(target, source, force=args.force)


if __name__ == "__main__":
    main()
