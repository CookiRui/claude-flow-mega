#!/usr/bin/env python3
"""
Repo Map Generator — Inspired by Aider's Repo Map approach.

Usage:
    python scripts/repo-map.py                    # Scan current directory
    python scripts/repo-map.py /path/to/project   # Scan specific directory
    python scripts/repo-map.py --format md         # Output Markdown (for CLAUDE.md)
    python scripts/repo-map.py --format json       # Output JSON (for programmatic use)

How it works:
    Uses regex to extract class/function/method definitions (lightweight, no dependencies required).
    Optionally counts reference relationships and ranks symbols by usage frequency.

Output:
    .repo-map.json  — Symbol index (JSON format)
    .repo-map.md    — Human-readable code map (Markdown format)
"""

import argparse
import json
import os
import re
from collections import defaultdict
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

# Directories to ignore
IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", "dist", "build",
    "bin", "obj", "target", ".venv", "venv", "vendor", "Packages",
    "Library", "Temp", "Logs", "UserSettings",
}

# ============================================================
# Core Logic
# ============================================================

def scan_files(root: str) -> list:
    """Scan for source code files."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter ignored directories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for filename in filenames:
            ext = Path(filename).suffix
            if ext in LANGUAGE_PATTERNS:
                files.append(os.path.join(dirpath, filename))
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
                # Skip common noise names
                if name in ("__init__", "__str__", "__repr__", "main", "test"):
                    continue
                symbols.append({
                    "name": name,
                    "type": symbol_type,
                    "file": rel_path,
                    "line": line_num,
                })
    return symbols


def count_references(symbols: list, files: list, root: str) -> dict:
    """Count how many times each symbol is referenced."""
    ref_count = defaultdict(int)
    symbol_names = {s["name"] for s in symbols}

    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            continue

        for name in symbol_names:
            # Simple word-boundary matching
            count = len(re.findall(r"\b" + re.escape(name) + r"\b", content))
            if count > 1:  # Subtract the definition itself
                ref_count[name] += count - 1

    return ref_count


def build_repo_map(root: str, count_refs: bool = True) -> dict:
    """Build the repository map."""
    files = scan_files(root)
    all_symbols = []

    for f in files:
        all_symbols.extend(extract_symbols(f, root))

    if count_refs:
        ref_count = count_references(all_symbols, files, root)
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


# ============================================================
# Output Formatters
# ============================================================

def format_json(repo_map: dict) -> str:
    return json.dumps(repo_map, indent=2, ensure_ascii=False)


def format_markdown(repo_map: dict) -> str:
    lines = [
        f"# Repo Map",
        f"",
        f"Files: {repo_map['total_files']} | Symbols: {repo_map['total_symbols']}",
        f"",
    ]

    # Group by file
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
    parser = argparse.ArgumentParser(description="Repo Map Generator")
    parser.add_argument("root", nargs="?", default=".", help="Project root directory")
    parser.add_argument("--format", choices=["json", "md"], default="json", help="Output format")
    parser.add_argument("--output", "-o", help="Output file path (default: .repo-map.{format})")
    parser.add_argument("--no-refs", action="store_true", help="Skip reference counting (faster on large codebases)")

    args = parser.parse_args()
    root = os.path.abspath(args.root)

    print(f"Scanning: {root}")
    repo_map = build_repo_map(root, count_refs=not args.no_refs)
    print(f"Found {repo_map['total_files']} files, {repo_map['total_symbols']} symbols")

    if args.format == "json":
        content = format_json(repo_map)
        output = args.output or os.path.join(root, ".repo-map.json")
    else:
        content = format_markdown(repo_map)
        output = args.output or os.path.join(root, ".repo-map.md")

    with open(output, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated: {output}")

    # Show Top 20 most-referenced symbols
    top = [s for s in repo_map["symbols"] if s["references"] > 0][:20]
    if top:
        print(f"\nTop {len(top)} most-referenced symbols:")
        for s in top:
            print(f"  {s['name']:30s} {s['type']:12s} {s['file']}:{s['line']}  ({s['references']} refs)")


if __name__ == "__main__":
    main()
