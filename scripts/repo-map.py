#!/usr/bin/env python3
"""
Repo Map Generator — Layered code map for large-scale projects.

Usage:
    python scripts/repo-map.py                           # Full build: L0 + all L1s
    python scripts/repo-map.py --incremental             # Incremental update (git diff)
    python scripts/repo-map.py --level L0                # Generate L0 only
    python scripts/repo-map.py --level L1 --module net   # Generate L1 for one module
    python scripts/repo-map.py --list-modules            # List detected modules
    python scripts/repo-map.py --format md               # Legacy flat output (backward compat)
    python scripts/repo-map.py --format json             # Legacy flat JSON output

Layered output (.repo-map/ directory):
    L0.md               — Global overview (<100 lines), always injected into context
    modules/{name}.md   — Per-module symbol index (<200 lines), loaded on demand
    config.json         — Module configuration (user-editable)
    state.json          — Build state for incremental updates

How it works:
    Uses regex to extract class/function/method definitions (lightweight, no dependencies).
    Detects modules from top-level directories (configurable via config.json).
    Supports incremental updates based on git diff.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ============================================================
# Supported Languages and Extraction Patterns
# ============================================================

LANGUAGE_PATTERNS = {
    ".py": {
        "class": r"^class\s+(\w+)",
        "function": r"^def\s+(\w+)",
        "method": r"^\s+def\s+(\w+)",
    },
    ".ts": {
        "class": r"(?:export\s+)?class\s+(\w+)",
        "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        "interface": r"(?:export\s+)?interface\s+(\w+)",
    },
    ".tsx": {
        "class": r"(?:export\s+)?class\s+(\w+)",
        "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
        "component": r"(?:export\s+)?(?:const|let)\s+(\w+)\s*[=:]\s*(?:React\.)?(?:FC|memo|forwardRef)",
    },
    ".js": {
        "class": r"(?:export\s+)?class\s+(\w+)",
        "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
    },
    ".jsx": {
        "class": r"(?:export\s+)?class\s+(\w+)",
        "function": r"(?:export\s+)?(?:async\s+)?function\s+(\w+)",
    },
    ".cs": {
        "class": r"(?:public|private|internal|protected)?\s*(?:static\s+)?(?:partial\s+)?class\s+(\w+)",
        "interface": r"(?:public|private|internal)?\s*interface\s+(\w+)",
        "method": r"(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:override\s+)?(?:virtual\s+)?\w+(?:<[\w,\s]+>)?\s+(\w+)\s*\(",
        "enum": r"(?:public|private|internal)?\s*enum\s+(\w+)",
    },
    ".java": {
        "class": r"(?:public|private|protected)?\s*(?:static\s+)?(?:abstract\s+)?class\s+(\w+)",
        "interface": r"(?:public|private|protected)?\s*interface\s+(\w+)",
        "method": r"(?:public|private|protected)\s+(?:static\s+)?(?:abstract\s+)?\w+(?:<[\w,\s]+>)?\s+(\w+)\s*\(",
    },
    ".go": {
        "function": r"^func\s+(\w+)",
        "method": r"^func\s+\(\w+\s+\*?\w+\)\s+(\w+)",
        "struct": r"^type\s+(\w+)\s+struct",
        "interface": r"^type\s+(\w+)\s+interface",
    },
    ".rs": {
        "struct": r"(?:pub\s+)?struct\s+(\w+)",
        "enum": r"(?:pub\s+)?enum\s+(\w+)",
        "function": r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)",
        "trait": r"(?:pub\s+)?trait\s+(\w+)",
        "impl": r"impl(?:<[\w,\s]+>)?\s+(\w+)",
    },
}

# Directories to always ignore
IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "dist", "build",
    "bin", "obj", "target", ".venv", "venv", "vendor", "Packages",
    "Library", "Temp", "Logs", "UserSettings", ".repo-map",
}

# Top-level directories that are NOT modules (infrastructure/docs)
NON_MODULE_DIRS = {
    "docs", "doc", "tests", "test", "bin", "obj", "dist", "build",
    "scripts", "tools", "config", "configs", ".github", ".gitea",
    ".claude", ".claude-flow", "node_modules", "__pycache__",
}

# Noise symbol names to skip
NOISE_NAMES = {"__init__", "__str__", "__repr__", "main", "test", "setUp", "tearDown"}

# ============================================================
# Module Detection
# ============================================================

REPO_MAP_DIR = ".repo-map"
CONFIG_FILE = os.path.join(REPO_MAP_DIR, "config.json")
STATE_FILE = os.path.join(REPO_MAP_DIR, "state.json")


def load_config(root: str) -> dict:
    """Load .repo-map/config.json or return defaults."""
    config_path = os.path.join(root, CONFIG_FILE)
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"modules": {}, "exclude_dirs": [], "auto_detect": True}


def detect_modules(root: str, config: dict) -> list:
    """Detect modules from top-level directories and config.

    Returns list of dicts: [{"name": str, "paths": [str], "description": str}]
    """
    modules = []
    seen_names = set()

    # 1. Explicit modules from config
    for name, info in config.get("modules", {}).items():
        paths = info.get("paths", [name + "/"])
        desc = info.get("description", "")
        modules.append({"name": name, "paths": paths, "description": desc})
        seen_names.add(name)

    # 2. Auto-detect from top-level directories
    if config.get("auto_detect", True):
        exclude = set(config.get("exclude_dirs", []))
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            entries = []

        for entry in entries:
            if entry in seen_names:
                continue
            if entry.startswith("."):
                continue
            if entry.lower() in NON_MODULE_DIRS:
                continue
            if entry in IGNORE_DIRS:
                continue
            if entry in exclude:
                continue
            full_path = os.path.join(root, entry)
            if not os.path.isdir(full_path):
                continue
            # Check it has source files
            has_source = False
            for dirpath, dirnames, filenames in os.walk(full_path):
                dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
                for fn in filenames:
                    if Path(fn).suffix in LANGUAGE_PATTERNS:
                        has_source = True
                        break
                if has_source:
                    break
            if has_source:
                modules.append({"name": entry, "paths": [entry + "/"], "description": ""})

    # 3. Catch-all "_root" pseudo-module for files not in any named module
    # This captures root-level files and files in non-module dirs (scripts/, tests/, etc.)
    modules.append({"name": "_root", "paths": [""], "description": "Root-level & utility files"})

    return modules


def classify_file_to_module(filepath: str, modules: list) -> str:
    """Given a relative file path, return which module it belongs to.

    Checks named modules first, then falls back to "_root" if present.
    Returns module name, or "_unclassified" if no match.
    """
    fp = filepath.replace("\\", "/")

    # First pass: check named modules (not _root)
    for mod in modules:
        if mod["name"] == "_root":
            continue
        for mod_path in mod["paths"]:
            mod_path = mod_path.replace("\\", "/")
            if mod_path and (fp.startswith(mod_path) or fp.startswith(mod_path.rstrip("/"))):
                return mod["name"]

    # Fallback: _root catches everything else
    for mod in modules:
        if mod["name"] == "_root":
            return "_root"

    return "_unclassified"


# ============================================================
# File Scanning and Symbol Extraction (preserved from original)
# ============================================================

def scan_files(root: str, subdir: str = None) -> list:
    """Scan for source code files, optionally within a subdirectory."""
    scan_root = os.path.join(root, subdir) if subdir else root
    scan_root = os.path.normpath(scan_root)
    if not os.path.isdir(scan_root):
        return []
    files = []
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for filename in filenames:
            ext = Path(filename).suffix
            if ext in LANGUAGE_PATTERNS:
                files.append(os.path.normpath(os.path.join(dirpath, filename)))
    return files


def extract_symbols(filepath: str, root: str) -> list:
    """Extract symbol definitions from a file."""
    ext = Path(filepath).suffix
    patterns = LANGUAGE_PATTERNS.get(ext, {})
    if not patterns:
        return []

    symbols = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, IOError):
        return []

    rel_path = os.path.relpath(filepath, root).replace("\\", "/")

    for line_num, line in enumerate(lines, 1):
        for symbol_type, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                name = match.group(1)
                if name in NOISE_NAMES:
                    continue
                symbols.append({
                    "name": name,
                    "type": symbol_type,
                    "file": rel_path,
                    "line": line_num,
                })
    return symbols


def count_references_scoped(symbols: list, files: list, root: str) -> dict:
    """Count references for symbols within a scoped set of files."""
    ref_count = defaultdict(int)
    symbol_names = {s["name"] for s in symbols}

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        for name in symbol_names:
            count = len(re.findall(r"\b" + re.escape(name) + r"\b", content))
            if count > 1:
                ref_count[name] += count - 1

    return ref_count


# ============================================================
# State Management (for incremental builds)
# ============================================================

def load_state(root: str) -> dict:
    """Load .repo-map/state.json or return empty state."""
    state_path = os.path.join(root, STATE_FILE)
    if os.path.isfile(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(root: str, state: dict) -> None:
    """Write .repo-map/state.json."""
    state_path = os.path.join(root, STATE_FILE)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_current_commit(root: str) -> str:
    """Get current HEAD commit hash, or empty string if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=root, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return ""


def get_changed_files(root: str, last_commit: str) -> list:
    """Get files changed since last_commit using git diff.

    Includes staged, unstaged, and untracked files.
    Returns list of relative paths, or None if git unavailable (triggers full rebuild).
    """
    if not last_commit:
        return None

    changed = set()
    commands = [
        ["git", "diff", "--name-only", last_commit, "HEAD"],
        ["git", "diff", "--name-only"],
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
            return None

    return list(changed)


# ============================================================
# L0 Generation (Global Overview)
# ============================================================

def detect_primary_language(symbols: list) -> str:
    """Detect the primary language of a set of symbols based on file extensions."""
    ext_count = defaultdict(int)
    seen_files = set()
    ext_to_lang = {
        ".py": "Python", ".ts": "TypeScript", ".tsx": "TSX", ".js": "JavaScript",
        ".jsx": "JSX", ".cs": "C#", ".java": "Java", ".go": "Go", ".rs": "Rust",
    }
    for s in symbols:
        f = s["file"]
        if f not in seen_files:
            seen_files.add(f)
            ext = Path(f).suffix
            if ext in ext_to_lang:
                ext_count[ext_to_lang[ext]] += 1
    if not ext_count:
        return "-"
    return max(ext_count, key=ext_count.get)


def compute_cross_module_refs(module_symbols: dict, files_by_module: dict, root: str) -> list:
    """Compute cross-module reference counts.

    For each module, collect its symbol names, then scan other modules' files
    for those names. Returns [(source_module, target_module, count)] where
    source references symbols defined in target.
    """
    # Collect symbol names per module
    names_by_module = {}
    for mod_name, symbols in module_symbols.items():
        names_by_module[mod_name] = {s["name"] for s in symbols}

    cross_refs = []
    for source_mod, source_files in files_by_module.items():
        # Read all source module files
        content_cache = ""
        for fp in source_files:
            try:
                with open(fp, "r", encoding="utf-8", errors="replace") as f:
                    content_cache += f.read() + "\n"
            except (OSError, IOError):
                continue

        for target_mod, target_names in names_by_module.items():
            if source_mod == target_mod:
                continue
            count = 0
            for name in target_names:
                matches = len(re.findall(r"\b" + re.escape(name) + r"\b", content_cache))
                if matches > 0:
                    count += matches
            if count > 0:
                cross_refs.append((source_mod, target_mod, count))

    # Sort by count descending
    cross_refs.sort(key=lambda x: x[2], reverse=True)
    return cross_refs


def generate_l0(root: str, modules: list, module_symbols: dict,
                module_file_counts: dict, cross_refs: list, commit: str) -> str:
    """Generate L0 markdown — global project overview."""
    now = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# Project Map (L0)",
        "",
        f"Generated: {now} | Commit: {commit or 'N/A'}",
        "",
        "| Module | Files | Symbols | Language | Description |",
        "|--------|-------|---------|----------|-------------|",
    ]

    for mod in modules:
        name = mod["name"]
        syms = module_symbols.get(name, [])
        fcount = module_file_counts.get(name, 0)
        lang = detect_primary_language(syms)
        desc = mod.get("description", "")
        lines.append(f"| {name} | {fcount} | {len(syms)} | {lang} | {desc} |")

    # Key entry points: top 3 most-referenced symbols per module
    lines.append("")
    lines.append("## Key Entry Points")
    for mod in modules:
        name = mod["name"]
        syms = module_symbols.get(name, [])
        top = sorted(syms, key=lambda s: s.get("references", 0), reverse=True)[:3]
        top_names = [f"`{s['name']}`" for s in top if s.get("references", 0) > 0]
        if not top_names:
            top_names = [f"`{s['name']}`" for s in syms[:3]]
        if top_names:
            lines.append(f"- **{name}**: {', '.join(top_names)}")

    # Cross-module dependencies (top 10)
    if cross_refs:
        lines.append("")
        lines.append("## Cross-Module Dependencies")
        for src, tgt, count in cross_refs[:10]:
            lines.append(f"- {src} -> {tgt} ({count} refs)")

    lines.append("")
    return "\n".join(lines)


# ============================================================
# L1 Generation (Per-Module Symbol Index)
# ============================================================

def generate_l1(root: str, module: dict, symbols: list,
                file_count: int, commit: str) -> str:
    """Generate L1 markdown for a single module."""
    now = datetime.now().strftime("%Y-%m-%d")
    name = module["name"]

    lines = [
        f"# Module: {name} (L1)",
        "",
        f"Generated: {now} | Files: {file_count} | Symbols: {len(symbols)}",
        "",
    ]

    # Group by file
    by_file = defaultdict(list)
    for s in symbols:
        by_file[s["file"]].append(s)

    for filepath in sorted(by_file.keys()):
        file_symbols = by_file[filepath]
        lines.append(f"## {filepath}")
        lines.append("")
        for s in sorted(file_symbols, key=lambda x: x["line"]):
            ref_str = f" ({s['references']} refs)" if s.get("references", 0) > 0 else ""
            lines.append(f"- `{s['type']}` **{s['name']}** L{s['line']}{ref_str}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# Layered Build
# ============================================================

def build_module_data(root: str, modules: list, count_refs: bool = True,
                      only_modules: set = None) -> tuple:
    """Build symbol data for all (or specified) modules.

    Returns (module_symbols, module_file_counts, files_by_module).
    """
    module_symbols = {}
    module_file_counts = {}
    files_by_module = {}

    # First pass: always collect files for named modules (needed for _root exclusion)
    named_module_files = set()
    for mod in modules:
        name = mod["name"]
        if name == "_root":
            continue

        mod_files = []
        for mod_path in mod["paths"]:
            mod_files.extend(scan_files(root, mod_path if mod_path else None))

        files_by_module[name] = mod_files
        named_module_files.update(mod_files)

    # Second pass: _root gets all remaining files
    has_root = any(m["name"] == "_root" for m in modules)
    if has_root and (not only_modules or "_root" in only_modules):
        all_files = scan_files(root)
        root_files = [f for f in all_files if f not in named_module_files]
        files_by_module["_root"] = root_files

    # Third pass: extract symbols and count references
    for mod in modules:
        name = mod["name"]
        if only_modules and name not in only_modules:
            continue
        if name not in files_by_module:
            continue
        mod_files = files_by_module[name]
        module_file_counts[name] = len(mod_files)

        # Extract symbols
        all_syms = []
        for fp in mod_files:
            all_syms.extend(extract_symbols(fp, root))

        # Count references within module scope
        if count_refs and all_syms:
            ref_count = count_references_scoped(all_syms, mod_files, root)
            for s in all_syms:
                s["references"] = ref_count.get(s["name"], 0)
        else:
            for s in all_syms:
                s["references"] = 0

        module_symbols[name] = all_syms

    return module_symbols, module_file_counts, files_by_module


def build_layered_map(root: str, incremental: bool = False, force: bool = False,
                      level: str = None, only_module: str = None,
                      count_refs: bool = True) -> None:
    """Main entry: detect modules, generate L0 + L1s, write to .repo-map/."""
    config = load_config(root)
    modules = detect_modules(root, config)

    if not modules:
        print("No modules detected.", file=sys.stderr)
        sys.exit(1)

    # Determine which modules need rebuilding
    state = load_state(root)
    commit = get_current_commit(root)
    affected_modules = None

    if incremental and not force and state.get("last_commit"):
        changed_files = get_changed_files(root, state["last_commit"])
        if changed_files is not None:
            affected_modules = set()
            for cf in changed_files:
                mod_name = classify_file_to_module(cf, modules)
                if mod_name != "_unclassified":
                    affected_modules.add(mod_name)
            if not affected_modules:
                print("No modules affected by recent changes. Map is up to date.")
                return
            print(f"Incremental: updating {len(affected_modules)} module(s): {', '.join(sorted(affected_modules))}")

    if only_module:
        affected_modules = {only_module}

    # Build data
    module_symbols, module_file_counts, files_by_module = build_module_data(
        root, modules, count_refs=count_refs, only_modules=affected_modules
    )

    # For incremental builds, merge with cached data for unaffected modules
    if affected_modules:
        cached_symbols = state.get("module_symbols", {})
        cached_file_counts = state.get("module_file_counts", {})
        for mod in modules:
            name = mod["name"]
            if name not in affected_modules:
                if name in cached_symbols:
                    module_symbols[name] = cached_symbols[name]
                    module_file_counts[name] = cached_file_counts.get(name, 0)
                    files_by_module[name] = []  # Won't need files for cross-ref on cached

    # Ensure output directory exists
    map_dir = os.path.join(root, REPO_MAP_DIR)
    modules_dir = os.path.join(map_dir, "modules")
    os.makedirs(modules_dir, exist_ok=True)

    # Generate L1 files
    if level is None or level == "L1":
        target_modules = affected_modules or {m["name"] for m in modules}
        for mod in modules:
            if mod["name"] not in target_modules:
                continue
            syms = module_symbols.get(mod["name"], [])
            fcount = module_file_counts.get(mod["name"], 0)
            l1_content = generate_l1(root, mod, syms, fcount, commit)
            l1_path = os.path.join(modules_dir, f"{mod['name']}.md")
            with open(l1_path, "w", encoding="utf-8") as f:
                f.write(l1_content)
            print(f"  L1: {mod['name']} ({fcount} files, {len(syms)} symbols)")

    # Compute cross-module refs (only for full builds or L0 generation)
    cross_refs = []
    if (level is None or level == "L0") and not only_module:
        # Only compute if we have all module data
        if not affected_modules or len(module_symbols) == len(modules):
            cross_refs = compute_cross_module_refs(module_symbols, files_by_module, root)

    # Generate L0
    if level is None or level == "L0":
        l0_content = generate_l0(root, modules, module_symbols,
                                 module_file_counts, cross_refs, commit)
        l0_path = os.path.join(map_dir, "L0.md")
        with open(l0_path, "w", encoding="utf-8") as f:
            f.write(l0_content)
        total_files = sum(module_file_counts.values())
        total_symbols = sum(len(s) for s in module_symbols.values())
        print(f"  L0: {len(modules)} modules, {total_files} files, {total_symbols} symbols")

    # Save state
    # Serialize symbols without file content for caching
    serializable_symbols = {}
    for name, syms in module_symbols.items():
        serializable_symbols[name] = syms

    new_state = {
        "last_commit": commit,
        "last_generated": datetime.now().isoformat(),
        "module_symbols": serializable_symbols,
        "module_file_counts": dict(module_file_counts),
    }
    save_state(root, new_state)

    # Write default config if it doesn't exist
    config_path = os.path.join(root, CONFIG_FILE)
    if not os.path.isfile(config_path):
        default_config = {
            "modules": {},
            "exclude_dirs": [],
            "auto_detect": True,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        print(f"  Created default config: {CONFIG_FILE}")


# ============================================================
# Legacy Flat Output (backward compatibility)
# ============================================================

def build_flat_map(root: str, count_refs: bool = True) -> dict:
    """Legacy: build flat repo map (original behavior)."""
    files = scan_files(root)
    all_symbols = []

    for f in files:
        all_symbols.extend(extract_symbols(f, root))

    if count_refs:
        ref_count = count_references_scoped(all_symbols, files, root)
        for s in all_symbols:
            s["references"] = ref_count.get(s["name"], 0)
        all_symbols.sort(key=lambda s: s["references"], reverse=True)
    else:
        for s in all_symbols:
            s["references"] = 0

    return {
        "root": root,
        "total_files": len(files),
        "total_symbols": len(all_symbols),
        "symbols": all_symbols,
    }


def format_flat_json(repo_map: dict) -> str:
    return json.dumps(repo_map, indent=2, ensure_ascii=False)


def format_flat_markdown(repo_map: dict) -> str:
    lines = [
        "# Repo Map",
        "",
        f"Files: {repo_map['total_files']} | Symbols: {repo_map['total_symbols']}",
        "",
    ]

    by_file = defaultdict(list)
    for s in repo_map["symbols"]:
        by_file[s["file"]].append(s)

    for filepath in sorted(by_file.keys()):
        symbols = by_file[filepath]
        lines.append(f"## {filepath}")
        lines.append("")
        for s in sorted(symbols, key=lambda x: x["line"]):
            ref_str = f" ({s['references']} refs)" if s["references"] > 0 else ""
            lines.append(f"- `{s['type']}` **{s['name']}** L{s['line']}{ref_str}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Repo Map Generator — Layered code map for large-scale projects"
    )
    parser.add_argument("root", nargs="?", default=".", help="Project root directory")
    parser.add_argument("--format", choices=["json", "md"], default=None,
                        help="Legacy flat output format (bypasses layered generation)")
    parser.add_argument("--output", "-o", help="Output file path (legacy mode only)")
    parser.add_argument("--no-refs", action="store_true",
                        help="Skip reference counting (faster)")
    parser.add_argument("--incremental", action="store_true",
                        help="Only rescan files changed since last build")
    parser.add_argument("--force", action="store_true",
                        help="Force full rebuild even in incremental mode")
    parser.add_argument("--level", choices=["L0", "L1"],
                        help="Generate only a specific level")
    parser.add_argument("--module", help="Generate L1 for a specific module only")
    parser.add_argument("--list-modules", action="store_true",
                        help="List detected modules and exit")

    args = parser.parse_args()
    root = os.path.abspath(args.root)

    # --- List modules mode ---
    if args.list_modules:
        config = load_config(root)
        modules = detect_modules(root, config)
        if not modules:
            print("No modules detected.")
            sys.exit(0)
        print(f"Detected {len(modules)} module(s):")
        for mod in modules:
            desc = f" — {mod['description']}" if mod.get("description") else ""
            paths = ", ".join(mod["paths"])
            print(f"  {mod['name']:20s} [{paths}]{desc}")
        sys.exit(0)

    # --- Legacy flat output mode ---
    if args.format is not None:
        print(f"Scanning: {root}")
        repo_map = build_flat_map(root, count_refs=not args.no_refs)
        print(f"Found {repo_map['total_files']} files, {repo_map['total_symbols']} symbols")

        if args.format == "json":
            content = format_flat_json(repo_map)
            output = args.output or os.path.join(root, ".repo-map.json")
        else:
            content = format_flat_markdown(repo_map)
            output = args.output or os.path.join(root, ".repo-map.md")

        with open(output, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated: {output}")

        top = [s for s in repo_map["symbols"] if s["references"] > 0][:20]
        if top:
            print(f"\nTop {len(top)} most-referenced symbols:")
            for s in top:
                print(f"  {s['name']:30s} {s['type']:12s} {s['file']}:{s['line']}  ({s['references']} refs)")
        sys.exit(0)

    # --- Layered generation mode (default) ---
    print(f"Building layered code map: {root}")
    build_layered_map(
        root,
        incremental=args.incremental,
        force=args.force,
        level=args.level,
        only_module=args.module,
        count_refs=not args.no_refs,
    )
    print("Done.")


if __name__ == "__main__":
    main()
