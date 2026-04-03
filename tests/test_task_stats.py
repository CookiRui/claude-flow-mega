#!/usr/bin/env python3
"""Tests for scripts/task-stats.py — task stats summary from kanban.json."""

import json
import os
import sys

import pytest

# Allow importing from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from importlib import import_module

# Import the module (filename has a hyphen, so use importlib)
ts = import_module("task-stats")

load_kanban = ts.load_kanban
extract_stats = ts.extract_stats
format_oneline = ts.format_oneline
main = ts.main


# ============================================================
# Fixture data factory
# ============================================================

def make_kanban(tree=None, total=None, done=0, failed=0, running=0, pending=0,
                total_cost_usd=0.0):
    """Generate a kanban JSON dict with configurable summary and tree.

    If *tree* is None, defaults to an empty list.
    If *total* is None, it is computed as done + failed + running + pending.
    """
    if tree is None:
        tree = []
    if total is None:
        total = done + failed + running + pending
    return {
        "goal": "test goal",
        "start_time": "2026-01-01T00:00:00.000000",
        "updated_at": "2026-01-01T00:00:00.000000",
        "summary": {
            "total": total,
            "done": done,
            "failed": failed,
            "running": running,
            "pending": pending,
            "total_cost_usd": total_cost_usd,
        },
        "tree": tree,
    }


def write_kanban(base_dir, kanban_data):
    """Write kanban_data as .claude-flow/kanban.json under base_dir."""
    cf_dir = os.path.join(str(base_dir), ".claude-flow")
    os.makedirs(cf_dir, exist_ok=True)
    path = os.path.join(cf_dir, "kanban.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(kanban_data, f)
    return path


# ============================================================
# Test classes (to be filled by subsequent sub-tasks)
# ============================================================

class TestDefaultOutput:
    """Verify human-readable one-line output."""
    pass


class TestJsonOutput:
    """Verify --json flag produces parseable JSON with expected keys."""
    pass


class TestMissingKanban:
    """Verify non-zero exit when kanban.json does not exist."""
    pass


class TestEmptyTree:
    """Verify zero counts when tree is empty."""
    pass


class TestMixedStatuses:
    """Verify correct tallying with mixed task statuses."""
    pass
