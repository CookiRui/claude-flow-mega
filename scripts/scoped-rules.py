#!/usr/bin/env python3
"""
Module-Scoped Rules Loader — Load constitution and rules based on git diff scope.

Usage:
    python scripts/scoped-rules.py                          # Detect modules in current directory
    python scripts/scoped-rules.py --root /path/to/project  # Specify project root
    python scripts/scoped-rules.py --changed "src/auth/login.py,src/api/routes.py"
                                                            # Load rules for specific changed files
    python scripts/scoped-rules.py --diff                   # Auto-detect changed files via git diff
    python scripts/scoped-rules.py --list-modules           # List detected modules and exit
    python scripts/scoped-rules.py --format json            # Output as JSON (default)
    python scripts/scoped-rules.py --format md              # Output as Markdown

How it works:
    1. Detects modules: directories containing .claude/ subdirectory
    2. Given a set of changed files, determines which modules are affected
    3. Loads root constitution + affected module constitutions (module overrides root on conflict)
    4. Loads root rules + affected module rules (module rules take priority)
    5. Outputs merged constitution and rules in order of priority

Module detection:
    A directory is considered a "module" if it contains a .claude/ subdirectory.
    The project root is always the root module (scope: "root" or ".").
    Nested modules are supported (e.g., src/subsystem/.claude/).

Priority resolution:
    - Root constitution is always loaded (lowest priority)
    - Module constitutions inherit root constraints and can add module-specific ones
    - When root and module have a rule file with the same name, module version wins
    - Non-conflicting rules from both scopes are included
"""

import argparse
import json
import os
import subprocess
import sys


# ============================================================
# Module Detection
# ============================================================

def detect_modules(root: str) -> list:
    """Detect modules by finding directories with .claude/ subdirectories.

    Returns list of dicts:
        [{"name": str, "path": str (absolute), "rel_path": str (relative)}]

    The root itself is always included as the "." module.
    """
    root = os.path.abspath(root)
    modules = []

    # Root is always a module (if it has .claude/)
    root_claude = os.path.join(root, ".claude")
    if os.path.isdir(root_claude):
        modules.append({
            "name": ".",
            "path": root,
            "rel_path": ".",
        })

    # Walk subdirectories looking for .claude/ dirs
    for dirpath, dirnames, filenames in os.walk(root):
        # Don't descend into ignored directories
        dirnames[:] = [
            d for d in dirnames
            if d not in {".git", "node_modules", "__pycache__", ".venv",
                         "venv", "vendor", "dist", "build", "Temp",
                         "Library", "Logs"}
            and d != ".claude"  # Don't recurse into .claude itself
        ]

        for d in list(dirnames):
            child = os.path.join(dirpath, d)
            child_claude = os.path.join(child, ".claude")
            if os.path.isdir(child_claude):
                rel = os.path.relpath(child, root).replace("\\", "/")
                modules.append({
                    "name": d,
                    "path": child,
                    "rel_path": rel,
                })

    return modules


# ============================================================
# Affected Module Resolution
# ============================================================

def affected_modules(root: str, changed_files: list) -> list:
    """Given a list of changed file paths (relative to root), determine which modules are affected.

    A changed file affects the most specific module whose path is a prefix of the file path.
    Files not under any module directory fall under root (".").

    Returns list of module dicts (subset of detect_modules output).
    """
    if not changed_files:
        return []

    root = os.path.abspath(root)
    all_modules = detect_modules(root)

    # Sort modules by path depth (deepest first) for most-specific matching
    non_root = [m for m in all_modules if m["name"] != "."]
    non_root.sort(key=lambda m: m["rel_path"].count("/"), reverse=True)
    root_module = next((m for m in all_modules if m["name"] == "."), None)

    affected = set()
    for cf in changed_files:
        cf_normalized = cf.replace("\\", "/")
        matched = False
        for mod in non_root:
            prefix = mod["rel_path"] + "/"
            if cf_normalized.startswith(prefix) or cf_normalized == mod["rel_path"]:
                affected.add(mod["name"])
                matched = True
                break
        if not matched and root_module:
            affected.add(".")

    # Convert names back to module dicts
    result = [m for m in all_modules if m["name"] in affected]
    return result


# ============================================================
# Rule and Constitution Loading
# ============================================================

def load_module_constitution(root: str, module_name: str) -> dict:
    """Load the constitution for a module.

    Args:
        root: project root path
        module_name: "." for root, or module directory name

    Returns dict with keys: scope, file, content. Or None if no constitution exists.
    """
    root = os.path.abspath(root)
    all_modules = detect_modules(root)
    mod = next((m for m in all_modules if m["name"] == module_name), None)
    if not mod:
        return None

    const_path = os.path.join(mod["path"], ".claude", "constitution.md")
    if not os.path.isfile(const_path):
        return None

    try:
        with open(const_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError):
        return None

    scope = "root" if module_name == "." else module_name
    return {
        "scope": scope,
        "file": os.path.relpath(const_path, root).replace("\\", "/"),
        "content": content,
    }


def load_module_rules(root: str, module_name: str) -> list:
    """Load all rules from a module's .claude/rules/ directory.

    Returns list of dicts: [{"file": str, "scope": str, "content": str}]
    """
    root = os.path.abspath(root)
    all_modules = detect_modules(root)
    mod = next((m for m in all_modules if m["name"] == module_name), None)
    if not mod:
        return []

    rules_dir = os.path.join(mod["path"], ".claude", "rules")
    if not os.path.isdir(rules_dir):
        return []

    scope = "root" if module_name == "." else module_name
    rules = []
    try:
        for fn in sorted(os.listdir(rules_dir)):
            fp = os.path.join(rules_dir, fn)
            if not os.path.isfile(fp):
                continue
            if not fn.endswith(".md"):
                continue
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    content = f.read()
            except (OSError, IOError):
                continue
            rules.append({
                "file": fn,
                "scope": scope,
                "content": content,
            })
    except OSError:
        pass

    return rules


# ============================================================
# Rule Priority Merging
# ============================================================

def merge_rules(root_rules: list, module_rules: list) -> list:
    """Merge root and module rules with module taking priority on filename conflicts.

    When root and module have a rule file with the same name,
    the module version wins (overrides root).
    Non-conflicting rules from both scopes are included.

    Returns merged list of rule dicts.
    """
    merged = []
    seen_files = set()

    # Module rules take priority
    for r in module_rules:
        merged.append(r)
        seen_files.add(r["file"])

    # Add root rules that don't conflict
    for r in root_rules:
        if r["file"] not in seen_files:
            merged.append(r)

    return merged


# ============================================================
# Integration: Get Scoped Rules for Changed Files
# ============================================================

def get_scoped_rules(root: str, changed_files: list) -> dict:
    """Main entry: given changed files, return all applicable rules and constitutions.

    Returns dict:
    {
        "constitutions": [{"scope": str, "file": str, "content": str}],
        "rules": [{"file": str, "scope": str, "content": str}],
        "affected_modules": [str],
    }

    Constitutions are ordered: root first, then module-specific.
    Rules are merged with module priority.
    """
    root = os.path.abspath(root)
    affected = affected_modules(root, changed_files)
    affected_names = [m["name"] for m in affected]

    constitutions = []
    all_module_rules = []

    # Always load root constitution
    root_const = load_module_constitution(root, ".")
    if root_const:
        constitutions.append(root_const)

    # Load root rules
    root_rules = load_module_rules(root, ".")

    # Load affected module constitutions and rules
    for mod in affected:
        if mod["name"] == ".":
            continue  # Already loaded root
        mod_const = load_module_constitution(root, mod["name"])
        if mod_const:
            constitutions.append(mod_const)
        mod_rules = load_module_rules(root, mod["name"])
        all_module_rules.extend(mod_rules)

    # Merge rules
    merged_rules = merge_rules(root_rules, all_module_rules)

    return {
        "constitutions": constitutions,
        "rules": merged_rules,
        "affected_modules": affected_names,
    }


# ============================================================
# Git Integration
# ============================================================

def get_changed_files_from_git(root: str) -> list:
    """Get changed files from git diff (staged + unstaged + untracked).

    Returns list of relative paths, or empty list on error.
    """
    changed = set()
    commands = [
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--staged", "--name-only"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=root, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    line = line.strip()
                    if line:
                        changed.add(line.replace("\\", "/"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return sorted(changed)


# ============================================================
# Output Formatters
# ============================================================

def format_json(result: dict) -> str:
    """Format scoped rules as JSON."""
    return json.dumps(result, indent=2, ensure_ascii=False)


def format_markdown(result: dict) -> str:
    """Format scoped rules as Markdown."""
    lines = [
        "# Scoped Rules",
        "",
        f"Affected modules: {', '.join(result['affected_modules']) or 'none'}",
        "",
    ]

    if result["constitutions"]:
        lines.append("## Constitutions")
        lines.append("")
        for c in result["constitutions"]:
            lines.append(f"### [{c['scope']}] {c['file']}")
            lines.append("")
            lines.append(c["content"])
            lines.append("")

    if result["rules"]:
        lines.append("## Rules")
        lines.append("")
        for r in result["rules"]:
            lines.append(f"### [{r['scope']}] {r['file']}")
            lines.append("")
            lines.append(r["content"])
            lines.append("")

    return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Module-Scoped Rules Loader — Load rules based on git diff scope"
    )
    parser.add_argument(
        "--root", default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--changed",
        help="Comma-separated list of changed file paths (relative to root)"
    )
    parser.add_argument(
        "--diff", action="store_true",
        help="Auto-detect changed files via git diff"
    )
    parser.add_argument(
        "--list-modules", action="store_true",
        help="List detected modules and exit"
    )
    parser.add_argument(
        "--format", choices=["json", "md"], default="json",
        help="Output format (default: json)"
    )

    args = parser.parse_args()
    root = os.path.abspath(args.root)

    if not os.path.isdir(root):
        print(f"Error: {root} is not a valid directory", file=sys.stderr)
        print("Usage: python scripts/scoped-rules.py --root /path/to/project", file=sys.stderr)
        sys.exit(1)

    # --- List modules mode ---
    if args.list_modules:
        modules = detect_modules(root)
        if not modules:
            print("No modules detected (no directories with .claude/ subdirectory).")
            sys.exit(0)
        print(f"Detected {len(modules)} module(s):")
        for mod in modules:
            const_exists = os.path.isfile(os.path.join(mod["path"], ".claude", "constitution.md"))
            rules_dir = os.path.join(mod["path"], ".claude", "rules")
            rule_count = len([f for f in os.listdir(rules_dir) if f.endswith(".md")]) if os.path.isdir(rules_dir) else 0
            const_str = "has constitution" if const_exists else "no constitution"
            print(f"  {mod['name']:20s} [{mod['rel_path']}] {const_str}, {rule_count} rule(s)")
        sys.exit(0)

    # --- Determine changed files ---
    if args.changed:
        changed_files = [f.strip() for f in args.changed.split(",") if f.strip()]
    elif args.diff:
        changed_files = get_changed_files_from_git(root)
        if not changed_files:
            print("No changed files detected.", file=sys.stderr)
            sys.exit(0)
        print(f"Changed files: {len(changed_files)}", file=sys.stderr)
    else:
        print("Error: specify --changed or --diff to determine scope.", file=sys.stderr)
        print("Usage: python scripts/scoped-rules.py --root . --diff", file=sys.stderr)
        print("       python scripts/scoped-rules.py --root . --changed 'src/auth/login.py'", file=sys.stderr)
        sys.exit(1)

    # --- Load and output scoped rules ---
    result = get_scoped_rules(root, changed_files)

    if args.format == "json":
        print(format_json(result))
    else:
        print(format_markdown(result))


if __name__ == "__main__":
    main()
