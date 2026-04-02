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
PlanningError = ps.PlanningError
Contract = ps.Contract
build_clarify_prompt = ps.build_clarify_prompt
build_plan_prompt = ps.build_plan_prompt
build_recursive_plan_prompt = ps.build_recursive_plan_prompt
parse_dag_response = ps.parse_dag_response
parse_recursive_dag_response = ps.parse_recursive_dag_response
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
# New RecursiveDAG method tests
# ============================================================

class TestGetLeafTasks:

    def test_all_leaves(self):
        """Tasks with no children are all leaves."""
        tasks = [
            RecursiveTask(id="a", description="", acceptance_criteria="", dependencies=[], files=[]),
            RecursiveTask(id="b", description="", acceptance_criteria="", dependencies=[], files=[]),
        ]
        dag = RecursiveDAG(tasks)
        leaves = dag.get_leaf_tasks()
        assert sorted(t.id for t in leaves) == ["a", "b"]

    def test_parent_excluded(self):
        """A task with children is not a leaf."""
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["c1"])
        child = RecursiveTask(id="c1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p")
        dag = RecursiveDAG([parent, child])
        leaves = dag.get_leaf_tasks()
        assert [t.id for t in leaves] == ["c1"]

    def test_empty_dag(self):
        dag = RecursiveDAG([])
        assert dag.get_leaf_tasks() == []


class TestGetChildren:

    def test_returns_direct_children(self):
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["c1", "c2"])
        c1 = RecursiveTask(id="c1", description="child1", acceptance_criteria="", dependencies=[], files=[], parent="p")
        c2 = RecursiveTask(id="c2", description="child2", acceptance_criteria="", dependencies=[], files=[], parent="p")
        dag = RecursiveDAG([parent, c1, c2])
        children = dag.get_children("p")
        assert sorted(c.id for c in children) == ["c1", "c2"]

    def test_nonexistent_task(self):
        dag = RecursiveDAG([])
        assert dag.get_children("nope") == []

    def test_task_with_no_children(self):
        t = RecursiveTask(id="t", description="", acceptance_criteria="", dependencies=[], files=[])
        dag = RecursiveDAG([t])
        assert dag.get_children("t") == []

    def test_missing_child_id_skipped(self):
        """If a child ID is listed but doesn't exist in the DAG, skip it."""
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["missing"])
        dag = RecursiveDAG([parent])
        assert dag.get_children("p") == []


class TestGetSubtree:

    def test_single_task(self):
        t = RecursiveTask(id="t", description="", acceptance_criteria="", dependencies=[], files=[])
        dag = RecursiveDAG([t])
        subtree = dag.get_subtree("t")
        assert [s.id for s in subtree] == ["t"]

    def test_nested_subtree(self):
        root = RecursiveTask(id="r", description="", acceptance_criteria="", dependencies=[], files=[], children=["a"])
        a = RecursiveTask(id="a", description="", acceptance_criteria="", dependencies=[], files=[], parent="r", children=["b"])
        b = RecursiveTask(id="b", description="", acceptance_criteria="", dependencies=[], files=[], parent="a")
        dag = RecursiveDAG([root, a, b])
        subtree = dag.get_subtree("r")
        assert [s.id for s in subtree] == ["r", "a", "b"]

    def test_nonexistent_task(self):
        dag = RecursiveDAG([])
        assert dag.get_subtree("nope") == []

    def test_subtree_of_leaf(self):
        leaf = RecursiveTask(id="leaf", description="", acceptance_criteria="", dependencies=[], files=[])
        dag = RecursiveDAG([leaf])
        subtree = dag.get_subtree("leaf")
        assert len(subtree) == 1
        assert subtree[0].id == "leaf"


class TestPropagateStatus:

    def test_parent_marked_done_when_all_children_done(self):
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["c1", "c2"])
        c1 = RecursiveTask(id="c1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="done")
        c2 = RecursiveTask(id="c2", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="done")
        dag = RecursiveDAG([parent, c1, c2])
        dag.propagate_status()
        assert dag.tasks["p"].status == "done"

    def test_parent_not_done_if_child_pending(self):
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["c1", "c2"])
        c1 = RecursiveTask(id="c1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="done")
        c2 = RecursiveTask(id="c2", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="pending")
        dag = RecursiveDAG([parent, c1, c2])
        dag.propagate_status()
        assert dag.tasks["p"].status == "pending"

    def test_multi_level_propagation(self):
        """Grandparent should be marked done if all descendants are done."""
        gp = RecursiveTask(id="gp", description="", acceptance_criteria="", dependencies=[], files=[], children=["p"])
        p = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], parent="gp", children=["c"])
        c = RecursiveTask(id="c", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="done")
        dag = RecursiveDAG([gp, p, c])
        dag.propagate_status()
        assert dag.tasks["p"].status == "done"
        assert dag.tasks["gp"].status == "done"

    def test_no_propagation_with_failed_child(self):
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["c1"])
        c1 = RecursiveTask(id="c1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="failed")
        dag = RecursiveDAG([parent, c1])
        dag.propagate_status()
        assert dag.tasks["p"].status == "pending"

    def test_thread_safety(self):
        """Concurrent propagate_status calls should not corrupt state."""
        import threading
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["c1", "c2"])
        c1 = RecursiveTask(id="c1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="done")
        c2 = RecursiveTask(id="c2", description="", acceptance_criteria="", dependencies=[], files=[], parent="p", status="done")
        dag = RecursiveDAG([parent, c1, c2])
        threads = [threading.Thread(target=dag.propagate_status) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert dag.tasks["p"].status == "done"


class TestReplaceSubtree:

    def test_basic_replacement(self):
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["old1", "old2"])
        old1 = RecursiveTask(id="old1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p")
        old2 = RecursiveTask(id="old2", description="", acceptance_criteria="", dependencies=[], files=[], parent="p")
        dag = RecursiveDAG([parent, old1, old2])

        new_children = [
            RecursiveTask(id="new1", description="new child 1", acceptance_criteria="", dependencies=[], files=[]),
            RecursiveTask(id="new2", description="new child 2", acceptance_criteria="", dependencies=[], files=[]),
        ]
        dag.replace_subtree("p", new_children)

        assert "old1" not in dag.tasks
        assert "old2" not in dag.tasks
        assert "new1" in dag.tasks
        assert "new2" in dag.tasks
        assert dag.tasks["p"].children == ["new1", "new2"]
        assert dag.tasks["new1"].parent == "p"
        assert dag.tasks["new2"].parent == "p"

    def test_downstream_dependency_remapping(self):
        """Tasks depending on removed children should depend on the parent instead."""
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["old1"])
        old1 = RecursiveTask(id="old1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p")
        downstream = RecursiveTask(id="down", description="", acceptance_criteria="", dependencies=["old1"], files=[])
        dag = RecursiveDAG([parent, old1, downstream])

        new_children = [
            RecursiveTask(id="new1", description="", acceptance_criteria="", dependencies=[], files=[]),
        ]
        dag.replace_subtree("p", new_children)

        assert dag.tasks["down"].dependencies == ["p"]

    def test_dedup_remapped_dependencies(self):
        """If a task depends on multiple removed IDs, they should be deduped to one parent ref."""
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], children=["old1", "old2"])
        old1 = RecursiveTask(id="old1", description="", acceptance_criteria="", dependencies=[], files=[], parent="p")
        old2 = RecursiveTask(id="old2", description="", acceptance_criteria="", dependencies=[], files=[], parent="p")
        downstream = RecursiveTask(id="down", description="", acceptance_criteria="", dependencies=["old1", "old2"], files=[])
        dag = RecursiveDAG([parent, old1, old2, downstream])

        dag.replace_subtree("p", [])

        assert dag.tasks["down"].dependencies == ["p"]

    def test_deep_descendants_removed(self):
        """Grandchildren should also be removed."""
        root = RecursiveTask(id="r", description="", acceptance_criteria="", dependencies=[], files=[], children=["c"])
        c = RecursiveTask(id="c", description="", acceptance_criteria="", dependencies=[], files=[], parent="r", children=["gc"])
        gc = RecursiveTask(id="gc", description="", acceptance_criteria="", dependencies=[], files=[], parent="c")
        dag = RecursiveDAG([root, c, gc])

        dag.replace_subtree("r", [
            RecursiveTask(id="new1", description="", acceptance_criteria="", dependencies=[], files=[]),
        ])

        assert "c" not in dag.tasks
        assert "gc" not in dag.tasks
        assert "new1" in dag.tasks

    def test_nonexistent_task_noop(self):
        dag = RecursiveDAG([])
        dag.replace_subtree("nope", [])  # should not raise

    def test_new_children_depth_set(self):
        parent = RecursiveTask(id="p", description="", acceptance_criteria="", dependencies=[], files=[], depth=2, children=[])
        dag = RecursiveDAG([parent])
        new_child = RecursiveTask(id="nc", description="", acceptance_criteria="", dependencies=[], files=[])
        dag.replace_subtree("p", [new_child])
        assert dag.tasks["nc"].depth == 3


class TestToKanbanDict:

    def test_basic_structure(self):
        t1 = RecursiveTask(id="t1", description="task one", acceptance_criteria="", dependencies=[], files=[], status="done", cost_usd=0.05, complexity=2)
        t2 = RecursiveTask(id="t2", description="task two", acceptance_criteria="", dependencies=[], files=[], status="pending", cost_usd=0.0, complexity=1)
        dag = RecursiveDAG([t1, t2])
        kanban = dag.to_kanban_dict()

        assert "summary" in kanban
        assert "tree" in kanban
        assert kanban["summary"]["total"] == 2
        assert kanban["summary"]["done"] == 1
        assert kanban["summary"]["pending"] == 1
        assert kanban["summary"]["total_cost_usd"] == 0.05

    def test_nested_tree(self):
        parent = RecursiveTask(id="p", description="parent", acceptance_criteria="", dependencies=[], files=[], children=["c1"], complexity=3, cost_usd=0.0)
        child = RecursiveTask(id="c1", description="child", acceptance_criteria="", dependencies=[], files=[], parent="p", complexity=1, cost_usd=0.02)
        dag = RecursiveDAG([parent, child])
        kanban = dag.to_kanban_dict()

        assert len(kanban["tree"]) == 1
        root_node = kanban["tree"][0]
        assert root_node["id"] == "p"
        assert len(root_node["children"]) == 1
        assert root_node["children"][0]["id"] == "c1"
        assert root_node["children"][0]["cost_usd"] == 0.02

    def test_empty_dag(self):
        dag = RecursiveDAG([])
        kanban = dag.to_kanban_dict()
        assert kanban["summary"]["total"] == 0
        assert kanban["tree"] == []

    def test_node_fields(self):
        """Each node must have id, description, status, complexity, cost_usd, commit_hash, children."""
        t = RecursiveTask(id="t1", description="d", acceptance_criteria="", dependencies=[], files=[], complexity=4, cost_usd=0.1, commit_hash="abc123")
        dag = RecursiveDAG([t])
        node = dag.to_kanban_dict()["tree"][0]
        assert node["id"] == "t1"
        assert node["description"] == "d"
        assert node["status"] == "pending"
        assert node["complexity"] == 4
        assert node["cost_usd"] == 0.1
        assert node["commit_hash"] == "abc123"
        assert node["children"] == []


class TestMarkFailedUnconditional:

    def test_no_retry_logic(self):
        """mark_failed should set failed immediately regardless of retries remaining."""
        t = RecursiveTask(id="t1", description="", acceptance_criteria="", dependencies=[], files=[], max_retries=5, retries=0)
        dag = RecursiveDAG([t])
        dag.mark_failed("t1", error_summary="boom")
        assert dag.tasks["t1"].status == "failed"
        assert dag.tasks["t1"].retries == 0  # retries not incremented by mark_failed

    def test_error_summary_stored(self):
        t = RecursiveTask(id="t1", description="", acceptance_criteria="", dependencies=[], files=[])
        dag = RecursiveDAG([t])
        dag.mark_failed("t1", error_summary="OOM killed")
        assert dag.tasks["t1"].error_summary == "OOM killed"

    def test_result_stored(self):
        t = RecursiveTask(id="t1", description="", acceptance_criteria="", dependencies=[], files=[])
        dag = RecursiveDAG([t])
        dag.mark_failed("t1", error_summary="err", result={"cost_usd": 0.03})
        assert dag.tasks["t1"].result == {"cost_usd": 0.03}

    def test_nonexistent_task_noop(self):
        dag = RecursiveDAG([])
        dag.mark_failed("nope", error_summary="test")  # should not raise

    def test_already_done_task_becomes_failed(self):
        """mark_failed overwrites any existing status."""
        t = RecursiveTask(id="t1", description="", acceptance_criteria="", dependencies=[], files=[], status="done")
        dag = RecursiveDAG([t])
        dag.mark_failed("t1", error_summary="rollback")
        assert dag.tasks["t1"].status == "failed"


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


# ============================================================
# parse_recursive_dag_response tests
# ============================================================

class TestParseRecursiveDagResponse:

    def test_valid_json_with_complexity(self):
        response = '''```json
[
  {"id": "t1", "description": "do X", "acceptance_criteria": "X done",
   "dependencies": [], "files": ["a.py"], "complexity": 2},
  {"id": "t2", "description": "do Y", "acceptance_criteria": "Y done",
   "dependencies": ["t1"], "files": ["b.py"], "complexity": 4}
]
```'''
        tasks = parse_recursive_dag_response(response)
        assert len(tasks) == 2
        assert tasks[0].id == "t1"
        assert tasks[0].complexity == 2
        assert tasks[1].complexity == 4
        assert tasks[1].dependencies == ["t1"]

    def test_complexity_out_of_range_raises(self):
        response = '''```json
[{"id": "t1", "description": "d", "acceptance_criteria": "a",
  "dependencies": [], "files": [], "complexity": 7}]
```'''
        with pytest.raises(PlanningError, match="invalid complexity"):
            parse_recursive_dag_response(response)

    def test_complexity_zero_raises(self):
        response = '''```json
[{"id": "t1", "description": "d", "acceptance_criteria": "a",
  "dependencies": [], "files": [], "complexity": 0}]
```'''
        with pytest.raises(PlanningError, match="invalid complexity"):
            parse_recursive_dag_response(response)

    def test_complexity_string_raises(self):
        response = '''```json
[{"id": "t1", "description": "d", "acceptance_criteria": "a",
  "dependencies": [], "files": [], "complexity": "high"}]
```'''
        with pytest.raises(PlanningError, match="invalid complexity"):
            parse_recursive_dag_response(response)

    def test_complexity_missing_raises(self):
        response = '''```json
[{"id": "t1", "description": "d", "acceptance_criteria": "a",
  "dependencies": [], "files": []}]
```'''
        with pytest.raises(PlanningError, match="invalid complexity"):
            parse_recursive_dag_response(response)

    def test_malformed_json_raises(self):
        response = '```json\n{not valid json\n```'
        with pytest.raises(PlanningError, match="Invalid JSON"):
            parse_recursive_dag_response(response)

    def test_no_json_fence_raises(self):
        response = "just some text without json"
        with pytest.raises(PlanningError, match="No.*json.*fence"):
            parse_recursive_dag_response(response)

    def test_non_array_raises(self):
        response = '```json\n{"id": "single"}\n```'
        with pytest.raises(PlanningError, match="must be an array"):
            parse_recursive_dag_response(response)

    def test_id_prefixing_with_parent_id(self):
        response = '''```json
[
  {"id": "a", "description": "d", "acceptance_criteria": "a",
   "dependencies": [], "files": [], "complexity": 1},
  {"id": "b", "description": "d", "acceptance_criteria": "a",
   "dependencies": ["a"], "files": [], "complexity": 2}
]
```'''
        tasks = parse_recursive_dag_response(response, parent_id="L0.T1")
        assert tasks[0].id == "L0.T1.a"
        assert tasks[1].id == "L0.T1.b"
        assert tasks[1].dependencies == ["L0.T1.a"]

    def test_no_parent_id_no_prefix(self):
        response = '''```json
[{"id": "x", "description": "d", "acceptance_criteria": "a",
  "dependencies": [], "files": [], "complexity": 1}]
```'''
        tasks = parse_recursive_dag_response(response, parent_id=None)
        assert tasks[0].id == "x"


# ============================================================
# build_recursive_plan_prompt tests
# ============================================================

class TestBuildRecursivePlanPrompt:

    def test_contains_complexity_requirement(self):
        prompt = build_recursive_plan_prompt("Build a feature", depth=0)
        assert "complexity" in prompt.lower()
        assert "[1, 5]" in prompt or "1 to 5" in prompt

    def test_contains_goal(self):
        prompt = build_recursive_plan_prompt("Fix the auth bug", depth=1)
        assert "Fix the auth bug" in prompt

    def test_includes_parent_contract(self):
        contract_md = "## Inputs\n- user data\n## Outputs\n- auth token"
        prompt = build_recursive_plan_prompt("Sub-task", depth=1, parent_contract=contract_md)
        assert "Parent Contract" in prompt
        assert "user data" in prompt
        assert "auth token" in prompt

    def test_no_parent_contract(self):
        prompt = build_recursive_plan_prompt("Task", depth=0, parent_contract=None)
        assert "Parent Contract" not in prompt

    def test_includes_depth_info(self):
        prompt = build_recursive_plan_prompt("Task", depth=3)
        assert "3" in prompt
        assert str(ps.MAX_RECURSION_DEPTH) in prompt


# ============================================================
# Contract tests
# ============================================================

class TestContract:

    def test_to_markdown(self):
        c = Contract(
            dag_id="task-1",
            inputs=["user config", "env vars"],
            outputs=["compiled binary"],
            constraints=["must use stdlib only"],
        )
        md = c.to_markdown()
        assert "# Contract: task-1" in md
        assert "- user config" in md
        assert "- compiled binary" in md
        assert "- must use stdlib only" in md

    def test_save_and_load_roundtrip(self, tmp_path):
        c = Contract(
            dag_id="T1.sub-2",
            inputs=["api schema"],
            outputs=["client code", "test stubs"],
            constraints=["no external deps"],
        )
        c.save(base_dir=str(tmp_path))

        loaded = Contract.load(str(tmp_path / "T1.sub-2.md"))
        assert loaded.dag_id == "T1.sub-2"
        assert loaded.inputs == ["api schema"]
        assert loaded.outputs == ["client code", "test stubs"]
        assert loaded.constraints == ["no external deps"]

    def test_empty_contract(self):
        c = Contract(dag_id="empty")
        md = c.to_markdown()
        assert "# Contract: empty" in md
        # Should still have section headers
        assert "## Inputs" in md
        assert "## Outputs" in md

    def test_save_creates_directory(self, tmp_path):
        subdir = str(tmp_path / "nested" / "contracts")
        c = Contract(dag_id="test", inputs=["x"], outputs=["y"], constraints=[])
        c.save(base_dir=subdir)
        assert os.path.isfile(os.path.join(subdir, "test.md"))


# ============================================================
# checkpoint_commit tests
# ============================================================

checkpoint_commit = ps.checkpoint_commit


class TestCheckpointCommit:

    def _make_task(self, task_id="t1", desc="Do something"):
        return RecursiveTask(
            id=task_id, description=desc,
            acceptance_criteria="done", dependencies=[], files=["a.py"],
        )

    @patch.object(ps.subprocess, "run")
    def test_success_commit_message(self, mock_run):
        """On success, commit message is 'checkpoint: {id} {desc}'."""
        def side_effect(cmd, **kw):
            r = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if "diff" in cmd and "--cached" in cmd:
                r.returncode = 1  # changes exist
            elif "rev-parse" in cmd:
                r.stdout = "abc1234"
            return r
        mock_run.side_effect = side_effect

        task = self._make_task()
        result = checkpoint_commit(task, success=True)

        # Check commit was called with correct message
        commit_calls = [c for c in mock_run.call_args_list
                        if c[0][0][1] == "commit"]
        assert len(commit_calls) == 1
        assert commit_calls[0][0][0][3] == "checkpoint: t1 Do something"
        assert result == "abc1234"
        assert task.commit_hash == "abc1234"

    @patch.object(ps.subprocess, "run")
    def test_failure_commit_message(self, mock_run):
        """On failure, commit message starts with '[FAILED] checkpoint:'."""
        def side_effect(cmd, **kw):
            r = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if "diff" in cmd and "--cached" in cmd:
                r.returncode = 1  # changes exist
            elif "rev-parse" in cmd:
                r.stdout = "def5678"
            return r
        mock_run.side_effect = side_effect

        task = self._make_task()
        result = checkpoint_commit(task, success=False)

        commit_calls = [c for c in mock_run.call_args_list
                        if c[0][0][1] == "commit"]
        assert len(commit_calls) == 1
        assert commit_calls[0][0][0][3] == "[FAILED] checkpoint: t1 Do something"
        assert result == "def5678"

    @patch.object(ps.subprocess, "run")
    def test_no_changes_returns_none(self, mock_run):
        """When there are no staged changes, returns None without committing."""
        def side_effect(cmd, **kw):
            # diff --cached --quiet returns 0 = no changes; all others succeed
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        mock_run.side_effect = side_effect

        task = self._make_task()
        result = checkpoint_commit(task, success=True)

        assert result is None
        # Should NOT have called git commit
        commit_calls = [c for c in mock_run.call_args_list
                        if len(c[0][0]) > 1 and c[0][0][1] == "commit"]
        assert len(commit_calls) == 0
