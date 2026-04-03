#!/usr/bin/env python3
"""
Task Stats — Print a one-line summary of task status from kanban.json.

Usage:
    python scripts/task-stats.py --target .
    python scripts/task-stats.py --file .claude-flow/kanban.json
    python scripts/task-stats.py --target . --json
"""

import argparse
import json
import os
import sys


def load_kanban(target_dir):
    """Load and return parsed kanban.json from the target directory."""
    kanban_path = os.path.join(target_dir, ".claude-flow", "kanban.json")
    if not os.path.isfile(kanban_path):
        print(
            f"Error: kanban.json not found at {kanban_path}\n"
            f"Usage: python scripts/task-stats.py --target /path/to/project\n"
            f"  --target: path to project directory containing .claude-flow/kanban.json (required)",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(kanban_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_stats(kanban):
    """Extract task statistics from kanban data."""
    summary = kanban.get("summary", {})
    return {
        "total": summary.get("total", 0),
        "done": summary.get("done", 0),
        "failed": summary.get("failed", 0),
        "pending": summary.get("pending", 0),
        "total_cost_usd": summary.get("total_cost_usd", 0.0),
    }


def format_oneline(stats):
    """Format stats as a human-readable one-line summary."""
    return (
        f"Tasks: {stats['total']} total, "
        f"{stats['done']} done, "
        f"{stats['failed']} failed, "
        f"{stats['pending']} pending | "
        f"Cost: ${stats['total_cost_usd']:.2f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Print a one-line summary of task status from kanban.json."
    )
    parser.add_argument(
        "--target",
        help="Path to project directory containing .claude-flow/kanban.json",
    )
    parser.add_argument(
        "--file",
        help="Path to kanban.json file directly (overrides --target)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON instead of human-readable text",
    )
    args = parser.parse_args()

    if args.file:
        if not os.path.isfile(args.file):
            print(
                f"Error: kanban file not found at {args.file}\n"
                f"Usage: python scripts/task-stats.py --file /path/to/kanban.json\n"
                f"  --file: path to kanban.json file (required if --target not given)",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            kanban = json.load(f)
    elif args.target:
        if not os.path.isdir(args.target):
            print(
                f"Error: {args.target} is not a valid directory\n"
                f"Usage: python scripts/task-stats.py --target /path/to/project\n"
                f"  --target: path to project directory (required if --file not given)",
                file=sys.stderr,
            )
            sys.exit(1)
        kanban = load_kanban(args.target)
    else:
        print(
            "Error: either --target or --file is required\n"
            "Usage: python scripts/task-stats.py --target /path/to/project\n"
            "       python scripts/task-stats.py --file /path/to/kanban.json",
            file=sys.stderr,
        )
        sys.exit(1)
    stats = extract_stats(kanban)

    if args.json_output:
        print(json.dumps(stats))
    else:
        print(format_oneline(stats))


if __name__ == "__main__":
    main()
