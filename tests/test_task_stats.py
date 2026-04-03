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

    def test_text_output_contains_all_fields(self, tmp_path, capsys):
        """main() with a valid kanban prints a line with total, done, failed, pending, cost."""
        kanban = make_kanban(done=3, failed=1, running=1, pending=2, total_cost_usd=1.25)
        write_kanban(tmp_path, kanban)

        # Patch sys.argv so argparse sees --target
        old_argv = sys.argv
        sys.argv = ["task-stats", "--target", str(tmp_path)]
        try:
            main()
        finally:
            sys.argv = old_argv

        out = capsys.readouterr().out
        # All summary fields must appear in the text output
        assert "7" in out          # total = 3+1+1+2
        assert "3" in out          # done
        assert "1" in out          # failed
        assert "2" in out          # pending
        assert "1.25" in out       # cost

    def test_exit_code_is_zero(self, tmp_path):
        """main() exits normally (no SystemExit) for a valid kanban."""
        kanban = make_kanban(done=1, pending=1, total_cost_usd=0.50)
        write_kanban(tmp_path, kanban)

        old_argv = sys.argv
        sys.argv = ["task-stats", "--target", str(tmp_path)]
        try:
            # Should NOT raise SystemExit
            main()
        finally:
            sys.argv = old_argv


class TestJsonOutput:
    """Verify --json flag produces parseable JSON with expected keys."""

    def test_json_output_is_parseable_with_correct_keys(self, tmp_path, capsys):
        """main() with --json prints valid JSON containing all expected keys with correct values."""
        kanban = make_kanban(done=5, failed=2, running=1, pending=3, total_cost_usd=4.56)
        write_kanban(tmp_path, kanban)

        old_argv = sys.argv
        sys.argv = ["task-stats", "--target", str(tmp_path), "--json"]
        try:
            main()
        finally:
            sys.argv = old_argv

        out = capsys.readouterr().out
        data = json.loads(out)  # must be valid JSON

        # All required keys exist
        for key in ("total", "done", "failed", "pending", "total_cost_usd"):
            assert key in data, f"Missing key: {key}"

        # Values match the kanban summary
        assert data["total"] == 11       # 5+2+1+3
        assert data["done"] == 5
        assert data["failed"] == 2
        assert data["pending"] == 3
        assert data["total_cost_usd"] == 4.56


class TestMissingKanban:
    """Verify non-zero exit when kanban.json does not exist."""

    def test_missing_kanban_exits_nonzero(self, tmp_path):
        """main() must raise SystemExit with a non-zero code when kanban.json is absent."""
        # tmp_path exists but has no .claude-flow/kanban.json inside it
        old_argv = sys.argv
        sys.argv = ["task-stats", "--target", str(tmp_path)]
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
        finally:
            sys.argv = old_argv

    def test_missing_kanban_prints_error_to_stderr(self, tmp_path, capsys):
        """main() must print an error message to stderr when kanban.json is missing."""
        old_argv = sys.argv
        sys.argv = ["task-stats", "--target", str(tmp_path)]
        try:
            with pytest.raises(SystemExit):
                main()
        finally:
            sys.argv = old_argv

        err = capsys.readouterr().err
        assert "kanban.json" in err.lower() or "not found" in err.lower()


class TestEmptyTree:
    """Verify zero counts when tree is empty."""
    pass


class TestMixedStatuses:
    """Verify correct tallying with mixed task statuses."""
    pass
