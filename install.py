#!/usr/bin/env python3
"""
claude-flow installer — One command to set up claude-flow in any project.

Usage:
    python install.py                              # Install to current directory (auto-detect presets)
    python install.py /path/to/project             # Install to specified directory
    python install.py --preset unity               # Force Unity preset on root (skip auto-detect)
    python install.py --force                      # Overwrite existing files
    python install.py --lang cn                    # Install Chinese (中文) templates

Auto-detection:
    The installer scans first-level subdirectories for known project types.
    Unity projects (containing Assets/ + ProjectSettings/) automatically get
    the Unity preset installed, while the root gets the core framework.

Remote usage (no clone needed):
    curl -sL https://raw.githubusercontent.com/<owner>/claude-flow/master/install.py | python3 - /path/to/project
"""

import argparse
import shutil
import sys
from pathlib import Path

AVAILABLE_PRESETS = ["unity"]
AVAILABLE_LANGS = ["en", "cn"]

# Preset auto-detection rules: preset_name -> detector function
PRESET_DETECTORS = {
    "unity": lambda d: (d / "Assets").is_dir() and (d / "ProjectSettings").is_dir(),
}

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
    ".claude/hooks/validate-bash.sh",
    ".claude/rules/coding-style.md",
    ".claude/rules/git-workflow.md",
    ".claude/rules/security.md",
    ".claude/rules/cli-tools.md",
    ".claude/skills/tdd/SKILL.md",
    ".claude/skills/verification/SKILL.md",
    ".claude/skills/brainstorming/SKILL.md",
    ".claude/skills/_template/SKILL.md",
    ".claude/skills/_template/references/detail.md",
    ".claude/commands/init-project.md",
    ".claude/commands/feature-plan-creator.md",
    ".claude/commands/bug-fix.md",
    ".claude/commands/deep-task.md",
    ".claude/commands/upgrade.md",
    ".claude/commands/autosolve.md",
]

SCRIPT_ITEMS = [
    "scripts/persistent-solve.py",
    "scripts/repo-map.py",
    "scripts/scope-loader.py",
    "scripts/lint-feedback.sh",
    "scripts/task-stats.py",
    "scripts/kanban-viewer.html",
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


def detect_presets(target: Path) -> dict:
    """Scan first-level subdirectories and detect project types.

    Returns:
        dict mapping subdir Path -> preset name
    """
    detected = {}
    for child in sorted(target.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        for preset_name, detector in PRESET_DETECTORS.items():
            if detector(child):
                detected[child] = preset_name
                break
    return detected


def copy_tree(src_dir: Path, target: Path, force: bool, installed: list, skipped: list):
    """Recursively copy all files from src_dir to target, preserving structure."""
    for src in src_dir.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(src_dir)
        dst = target / rel
        if dst.exists() and not force:
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        installed.append(str(rel))


def install_core(target: Path, source: Path, force: bool = False, lang: str = "en"):
    """Install core claude-flow files to the target directory."""
    if lang == "cn":
        template_dir = source / "template-cn"
        if not template_dir.is_dir():
            print(f"Error: Chinese template not found at {template_dir}")
            print("Falling back to English template.")
            template_dir = source / "template"
    else:
        template_dir = source / "template"

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

    return installed, skipped


def install_preset(target: Path, source: Path, preset: str, force: bool = False):
    """Install a preset overlay to the target directory."""
    preset_dir = source / "presets" / preset
    if not preset_dir.is_dir():
        print(f"Error: preset '{preset}' not found at {preset_dir}")
        sys.exit(1)

    installed = []
    skipped = []
    copy_tree(preset_dir, target, force=True, installed=installed, skipped=skipped)

    # Make shell scripts executable
    for item in installed:
        if item.endswith(".sh"):
            p = target / item
            p.chmod(p.stat().st_mode | 0o111)

    return installed, skipped


def print_results(label: str, installed: list, skipped: list, target: Path):
    """Print installation results for a target."""
    if installed:
        print(f"  Installed {len(installed)} files to {target}:")
        for f in installed:
            print(f"    + {f}")
    if skipped:
        print(f"  Skipped {len(skipped)} existing files (use --force to overwrite):")
        for f in skipped:
            print(f"    ~ {f}")
    if not installed and not skipped:
        print("  Nothing to install.")


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
    parser.add_argument(
        "--preset",
        choices=AVAILABLE_PRESETS,
        help="Force a specific preset on root directory (skip auto-detect)",
    )
    parser.add_argument(
        "--no-detect",
        action="store_true",
        help="Skip auto-detection of subdirectory project types",
    )
    parser.add_argument(
        "--lang",
        choices=AVAILABLE_LANGS,
        default="en",
        help="Template language: en (English, default) or cn (Chinese/中文)",
    )

    args = parser.parse_args()
    target = Path(args.target).resolve()
    source = find_source_dir()

    if not target.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {target}")

    # Step 1: Install core to root
    lang_label = " (中文)" if args.lang == "cn" else ""
    print(f"[core] Installing claude-flow{lang_label} to: {target}")
    core_installed, core_skipped = install_core(target, source, force=args.force, lang=args.lang)
    print_results("core", core_installed, core_skipped, target)

    # Step 2: Apply preset
    if args.preset:
        # Explicit preset: apply to root, skip auto-detect
        print(f"\n[preset] Applying '{args.preset}' to: {target}")
        p_installed, p_skipped = install_preset(target, source, args.preset, force=args.force)
        print_results(args.preset, p_installed, p_skipped, target)
    elif not args.no_detect:
        # Auto-detect subdirectory project types
        detected = detect_presets(target)
        if detected:
            for subdir, preset_name in detected.items():
                print(f"\n[auto-detect] Found {preset_name} project: {subdir.name}/")
                print(f"[preset] Applying '{preset_name}' to: {subdir}")
                p_installed, p_skipped = install_preset(subdir, source, preset_name, force=args.force)
                print_results(preset_name, p_installed, p_skipped, subdir)
        else:
            print("\n[auto-detect] No known project types detected in subdirectories.")

    print()
    print("Next steps:")
    print(f"  cd {target}")
    print("  claude")
    print("  > /init-project")
    print()
    print("This will auto-analyze your project and replace all template")
    print("placeholders with project-specific configuration.")


if __name__ == "__main__":
    main()
