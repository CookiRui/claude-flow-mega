#!/usr/bin/env python3
"""Tests for scripts/persistent-solve.py — DAG, budget, and clarification logic."""

import json
import sys
import os
from unittest.mock import patch

import pytest

# Allow importing from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from importlib import import_module

# Import the module (filename has a hyphen, so use importlib)
ps = import_module("persistent-solve")

RecursiveTask = ps.RecursiveTask
RecursiveDAG = ps.RecursiveDAG
BudgetTracker = ps.BudgetTracker
build_clarify_prompt = ps.build_clarify_prompt
build_plan_prompt = ps.build_plan_prompt
parse_dag_response = ps.parse_dag_response
clarify_goal = ps.clarify_goal


# ============================================================
# RecursiveDAG tests
# ============================================================

class TestRecursiveDAG:

    def _make_tasks(self):
        return [
            RecursiveTask(id="t1", description="first", acceptance_criteria="done",
                 dependencies=[], files=["a.py"]),
            RecursiveTask(id="t2", description="second", acceptance_criteria="done",
                 dependencies=["t1"], files=["b.py"]),
            RecursiveTask(id="t3", description="third", acceptance_criteria="done",
                 dependencies=["t1"], files=["c.py"]),
        ]

    def test_get_ready_leaves_initial(self):
        dag = RecursiveDAG(self._make_tasks())
        ready = dag.get_ready_leaves()
        assert [t.id for t in ready] == ["t1"]

    def test_get_ready_leaves_after_done(self):
        dag = RecursiveDAG(self._make_tasks())
        dag.mark_done("t1")
        ready = dag.get_ready_leaves()
        ids = sorted(t.id for t in ready)
        assert ids == ["t2", "t3"]

    def test_mark_failed_unconditional(self):
        dag = RecursiveDAG(self._make_tasks())
        dag.mark_failed("t1", error_summary="compile error")
        assert dag.tasks["t1"].status == "failed"
        assert dag.tasks["t1"].error_summary == "compile error"

    def test_has_ready_tasks(self):
        dag = RecursiveDAG(self._make_tasks())
        assert dag.has_ready_tasks()
        dag.tasks["t1"].status = "running"
        dag.tasks["t2"].status = "running"
        dag.tasks["t3"].status = "running"
        assert not dag.has_ready_tasks()

    def test_all_done(self):
        dag = RecursiveDAG(self._make_tasks())
        assert not dag.all_done()
        for t in dag.tasks.values():
            t.status = "done"
        assert dag.all_done()

    def test_parallel_groups_no_conflict(self):
        tasks = [
            RecursiveTask(id="a", description="", acceptance_criteria="",
                 dependencies=[], files=["x.py"]),
            RecursiveTask(id="b", description="", acceptance_criteria="",
                 dependencies=[], files=["y.py"]),
        ]
        dag = RecursiveDAG(tasks)
        parallel, sequential = dag.get_parallel_groups(list(dag.tasks.values()))
        assert len(parallel) == 2
        assert len(sequential) == 0

    def test_parallel_groups_with_conflict(self):
        tasks = [
            RecursiveTask(id="a", description="", acceptance_criteria="",
                 dependencies=[], files=["x.py"]),
            RecursiveTask(id="b", description="", acceptance_criteria="",
                 dependencies=[], files=["x.py"]),
        ]
        dag = RecursiveDAG(tasks)
        parallel, sequential = dag.get_parallel_groups(list(dag.tasks.values()))
        assert len(parallel) == 1
        assert len(sequential) == 1

    def test_parallel_groups_empty_files_sequential(self):
        """Tasks with empty files list are treated as sequential (unknown scope)."""
        tasks = [
            RecursiveTask(id="a", description="", acceptance_criteria="",
                 dependencies=[], files=[]),
            RecursiveTask(id="b", description="", acceptance_criteria="",
                 dependencies=[], files=["y.py"]),
        ]
        dag = RecursiveDAG(tasks)
        all_tasks = list(dag.tasks.values())
        parallel, sequential = dag.get_parallel_groups(all_tasks)
        empty_files_task = [t for t in sequential if t.id == "a"]
        assert len(empty_files_task) == 1 or len(parallel) <= 1

    def test_single_task_parallel(self):
        tasks = [RecursiveTask(id="a", description="", acceptance_criteria="",
                      dependencies=[], files=["x.py"])]
        dag = RecursiveDAG(tasks)
        parallel, sequential = dag.get_parallel_groups(list(dag.tasks.values()))
        assert len(parallel) == 1
        assert len(sequential) == 0

    def test_summary(self):
        dag = RecursiveDAG(self._make_tasks())
        dag.mark_done("t1", result={"cost_usd": 0.05})
        dag.mark_failed("t2", error_summary="timeout")
        text = dag.summary()
        assert "t1" in text and "done" in text
        assert "t2" in text and "failed" in text
        assert "t3" in text and "pending" in text


# ============================================================
# BudgetTracker tests
# ============================================================

class TestBudgetTracker:

    def test_initial_state(self):
        bt = BudgetTracker(10.0, 1.0)
        assert bt.remaining() == 10.0
        assert bt.can_afford()

    def test_record_and_remaining(self):
        bt = BudgetTracker(5.0, 0.5)
        bt.record("t1", 2.0)
        assert bt.remaining() == 3.0
        assert bt.total_spent == 2.0

    def test_budget_exhausted(self):
        bt = BudgetTracker(1.0, 0.5)
        bt.record("t1", 1.0)
        assert bt.remaining() == 0.0
        assert not bt.can_afford()

    def test_next_task_budget_capped(self):
        bt = BudgetTracker(5.0, 2.0)
        bt.record("t1", 4.5)
        assert bt.next_task_budget() == 0.5  # min(2.0, 0.5)

    def test_thread_safety(self):
        """Multiple threads recording costs should not lose data."""
        import threading
        bt = BudgetTracker(100.0, 1.0)
        threads = []
        for i in range(100):
            t = threading.Thread(target=bt.record, args=(f"t{i}", 0.1))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert abs(bt.total_spent - 10.0) < 0.001


# ============================================================
# parse_dag_response tests
# ============================================================

class TestParseDagResponse:

    def test_valid_json(self):
        response = '''Some text
```json
[
  {"id": "t1", "description": "do X", "acceptance_criteria": "X done",
   "dependencies": [], "files": ["a.py"]},
  {"id": "t2", "description": "do Y", "acceptance_criteria": "Y done",
   "dependencies": ["t1"], "files": ["b.py"]}
]
```
'''
        dag = parse_dag_response(response)
        assert len(dag.tasks) == 2
        assert "t1" in dag.tasks
        assert dag.tasks["t2"].dependencies == ["t1"]

    def test_no_json_fence_fallback(self):
        dag = parse_dag_response("no json here")
        assert len(dag.tasks) == 1
        assert dag.tasks["task-1"].description.startswith("no json")

    def test_invalid_json_fallback(self):
        response = '```json\n{not valid\n```'
        dag = parse_dag_response(response)
        assert len(dag.tasks) == 1

    def test_non_array_json_fallback(self):
        response = '```json\n{"id": "single"}\n```'
        dag = parse_dag_response(response)
        assert len(dag.tasks) == 1  # fallback

    def test_empty_response_fallback(self):
        dag = parse_dag_response("")
        assert len(dag.tasks) == 1


# ============================================================
# build_clarify_prompt tests
# ============================================================

class TestBuildClarifyPrompt:

    def test_contains_goal(self):
        prompt = build_clarify_prompt("Fix the login bug")
        assert "Fix the login bug" in prompt

    def test_asks_for_json(self):
        prompt = build_clarify_prompt("anything")
        assert "```json" in prompt
        assert '"clear"' in prompt
        assert '"questions"' in prompt


# ============================================================
# clarify_goal tests
# ============================================================

class TestClarifyGoal:

    def _mock_session(self, clear, confidence, questions=None, assumptions=None):
        """Build a mock run_claude_session return value."""
        assessment = {
            "clear": clear,
            "confidence": confidence,
            "questions": questions or [],
            "assumptions": assumptions or [],
        }
        return {
            "output": f'```json\n{json.dumps(assessment)}\n```',
            "cost_usd": 0.01,
            "success": True,
        }

    @patch.object(ps, "run_claude_session")
    def test_clear_goal_passes_through(self, mock_run):
        mock_run.return_value = self._mock_session(True, 0.9)
        bt = BudgetTracker(5.0, 0.5)
        result = clarify_goal("Clear specific goal", bt)
        assert result == "Clear specific goal"

    @patch("builtins.input", return_value="use PostgreSQL not MySQL")
    @patch.object(ps, "run_claude_session")
    def test_ambiguous_goal_asks_user(self, mock_run, mock_input):
        mock_run.return_value = self._mock_session(
            False, 0.4,
            questions=["Which database?"],
            assumptions=["Assume PostgreSQL"],
        )
        bt = BudgetTracker(5.0, 0.5)
        result = clarify_goal("Set up the database", bt)
        assert "use PostgreSQL not MySQL" in result
        assert "User clarification" in result

    @patch("builtins.input", return_value="")
    @patch.object(ps, "run_claude_session")
    def test_ambiguous_goal_accept_defaults(self, mock_run, mock_input):
        mock_run.return_value = self._mock_session(
            False, 0.4,
            questions=["Which database?"],
            assumptions=["Assume PostgreSQL"],
        )
        bt = BudgetTracker(5.0, 0.5)
        result = clarify_goal("Set up the database", bt)
        assert "Assumptions (accepted by user)" in result
        assert "Assume PostgreSQL" in result

    @patch("builtins.input", return_value="q")
    @patch.object(ps, "run_claude_session")
    def test_user_aborts(self, mock_run, mock_input):
        mock_run.return_value = self._mock_session(
            False, 0.3,
            questions=["What scope?"],
        )
        bt = BudgetTracker(5.0, 0.5)
        with pytest.raises(SystemExit):
            clarify_goal("Vague goal", bt)

    @patch.object(ps, "run_claude_session")
    def test_unparseable_response_passes_through(self, mock_run):
        mock_run.return_value = {
            "output": "I don't know what to say",
            "cost_usd": 0.01,
            "success": True,
        }
        bt = BudgetTracker(5.0, 0.5)
        result = clarify_goal("Some goal", bt)
        assert result == "Some goal"

    @patch.object(ps, "run_claude_session")
    def test_eof_on_input_passes_through(self, mock_run):
        """Non-interactive (no TTY) should proceed with original goal."""
        mock_run.return_value = self._mock_session(
            False, 0.3, questions=["What?"]
        )
        bt = BudgetTracker(5.0, 0.5)
        with patch("builtins.input", side_effect=EOFError):
            result = clarify_goal("A goal", bt)
        assert result == "A goal"

    @patch.object(ps, "run_claude_session")
    def test_budget_recorded(self, mock_run):
        mock_run.return_value = self._mock_session(True, 0.9)
        bt = BudgetTracker(5.0, 0.5)
        clarify_goal("Goal", bt)
        assert "clarification" in bt.task_costs
        assert bt.task_costs["clarification"] == 0.01
