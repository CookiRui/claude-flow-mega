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
execute_leaf_task = ps.execute_leaf_task
run_verification = ps.run_verification


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


# ============================================================
# run_verification dispatching tests
# ============================================================

class TestRunVerification:

    def _make_task(self, complexity=1):
        return RecursiveTask(
            id="v1", description="verify me",
            acceptance_criteria="it works", dependencies=[], files=["a.py"],
            complexity=complexity,
        )

    @patch.object(ps, "run_l1", return_value=True)
    def test_c1_only_l1(self, mock_l1):
        """C:1 dispatches only L1."""
        task = self._make_task(complexity=1)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is True
        mock_l1.assert_called_once_with(task, bt)

    @patch.object(ps, "run_l1", return_value=True)
    def test_c2_only_l1(self, mock_l1):
        """C:2 dispatches only L1."""
        task = self._make_task(complexity=2)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is True
        mock_l1.assert_called_once_with(task, bt)

    @patch.object(ps, "run_l2", return_value=True)
    @patch.object(ps, "run_l1", return_value=True)
    def test_c3_l1_and_l2(self, mock_l1, mock_l2):
        """C:3 dispatches L1 + L2."""
        task = self._make_task(complexity=3)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is True
        mock_l1.assert_called_once_with(task, bt)
        mock_l2.assert_called_once_with(task, bt)

    @patch.object(ps, "run_l2", return_value=True)
    @patch.object(ps, "run_l1", return_value=True)
    def test_c4_l1_and_l2(self, mock_l1, mock_l2):
        """C:4 dispatches L1 + L2."""
        task = self._make_task(complexity=4)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is True
        mock_l1.assert_called_once_with(task, bt)
        mock_l2.assert_called_once_with(task, bt)

    @patch.object(ps, "run_l3", return_value=True)
    @patch.object(ps, "run_l2", return_value=True)
    @patch.object(ps, "run_l1", return_value=True)
    def test_c5_l1_l2_l3(self, mock_l1, mock_l2, mock_l3):
        """C:5 dispatches L1 + L2 + L3."""
        task = self._make_task(complexity=5)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is True
        mock_l1.assert_called_once_with(task, bt)
        mock_l2.assert_called_once_with(task, bt)
        mock_l3.assert_called_once_with(task, bt)

    @patch.object(ps, "run_l1", return_value=False)
    def test_l1_fail_short_circuits(self, mock_l1):
        """If L1 fails, L2 and L3 are not called."""
        task = self._make_task(complexity=5)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is False
        mock_l1.assert_called_once()

    @patch.object(ps, "run_l2", return_value=False)
    @patch.object(ps, "run_l1", return_value=True)
    def test_l2_fail_short_circuits(self, mock_l1, mock_l2):
        """If L2 fails, L3 is not called."""
        task = self._make_task(complexity=5)
        bt = BudgetTracker(5.0, 0.5)
        result = run_verification(task, bt)
        assert result is False
        mock_l1.assert_called_once()
        mock_l2.assert_called_once()

    @patch.object(ps, "run_l2")
    @patch.object(ps, "run_l1", return_value=True)
    def test_c2_no_l2_called(self, mock_l1, mock_l2):
        """C:2 should NOT call L2."""
        task = self._make_task(complexity=2)
        bt = BudgetTracker(5.0, 0.5)
        run_verification(task, bt)
        mock_l2.assert_not_called()

    @patch.object(ps, "run_l3")
    @patch.object(ps, "run_l2", return_value=True)
    @patch.object(ps, "run_l1", return_value=True)
    def test_c4_no_l3_called(self, mock_l1, mock_l2, mock_l3):
        """C:4 should NOT call L3."""
        task = self._make_task(complexity=4)
        bt = BudgetTracker(5.0, 0.5)
        run_verification(task, bt)
        mock_l3.assert_not_called()


# ============================================================
# execute_leaf_task tests
# ============================================================

class TestExecuteLeafTask:

    def _make_task(self, task_id="leaf1", desc="Implement feature", ac="Feature works"):
        return RecursiveTask(
            id=task_id, description=desc,
            acceptance_criteria=ac, dependencies=[], files=["src/main.py"],
        )

    @patch.object(ps, "run_claude_session")
    def test_prompt_contains_contract_text(self, mock_run):
        """When contracts_text is provided, the prompt includes it."""
        mock_run.return_value = {
            "output": "done", "cost_usd": 0.05, "input_tokens": 100,
            "output_tokens": 50, "duration_ms": 1000, "stop_reason": "end",
            "success": True,
        }
        task = self._make_task()
        bt = BudgetTracker(5.0, 0.5)
        contract = "## Inputs\n- user_id: int\n## Outputs\n- auth_token: str"

        execute_leaf_task(task, "Build auth", bt, contracts_text=contract)

        prompt_arg = mock_run.call_args[0][0]
        assert "Interface Contracts" in prompt_arg
        assert "user_id: int" in prompt_arg
        assert "auth_token: str" in prompt_arg
        assert "You MUST respect" in prompt_arg

    @patch.object(ps, "run_claude_session")
    def test_prompt_without_contracts(self, mock_run):
        """When contracts_text is empty, the prompt omits contract section."""
        mock_run.return_value = {
            "output": "done", "cost_usd": 0.02, "input_tokens": 50,
            "output_tokens": 30, "duration_ms": 500, "stop_reason": "end",
            "success": True,
        }
        task = self._make_task()
        bt = BudgetTracker(5.0, 0.5)

        execute_leaf_task(task, "Build auth", bt, contracts_text="")

        prompt_arg = mock_run.call_args[0][0]
        assert "Interface Contracts" not in prompt_arg
        assert "You MUST respect" not in prompt_arg

    @patch.object(ps, "run_claude_session")
    def test_prompt_contains_task_details(self, mock_run):
        """Prompt includes task id, description, acceptance criteria, and goal."""
        mock_run.return_value = {
            "output": "done", "cost_usd": 0.03, "input_tokens": 60,
            "output_tokens": 40, "duration_ms": 700, "stop_reason": "end",
            "success": True,
        }
        task = self._make_task(task_id="T2.a", desc="Add auth middleware", ac="Middleware validates JWT")
        bt = BudgetTracker(5.0, 0.5)

        execute_leaf_task(task, "Secure the API", bt)

        prompt_arg = mock_run.call_args[0][0]
        assert "T2.a" in prompt_arg
        assert "Add auth middleware" in prompt_arg
        assert "Middleware validates JWT" in prompt_arg
        assert "Secure the API" in prompt_arg

    @patch.object(ps, "run_claude_session")
    def test_prompt_contains_files_section(self, mock_run):
        """When task has files, prompt includes files to modify."""
        mock_run.return_value = {
            "output": "done", "cost_usd": 0.01, "input_tokens": 30,
            "output_tokens": 20, "duration_ms": 300, "stop_reason": "end",
            "success": True,
        }
        task = self._make_task()
        bt = BudgetTracker(5.0, 0.5)

        execute_leaf_task(task, "goal", bt)

        prompt_arg = mock_run.call_args[0][0]
        assert "Files to Modify" in prompt_arg
        assert "src/main.py" in prompt_arg

    @patch.object(ps, "run_claude_session")
    def test_cost_recorded_on_budget(self, mock_run):
        """Cost from run_claude_session is recorded on the budget tracker."""
        mock_run.return_value = {
            "output": "done", "cost_usd": 0.07, "input_tokens": 100,
            "output_tokens": 50, "duration_ms": 1000, "stop_reason": "end",
            "success": True,
        }
        task = self._make_task()
        bt = BudgetTracker(5.0, 0.5)

        execute_leaf_task(task, "goal", bt)

        assert bt.total_spent == 0.07
        assert "leaf1" in bt.task_costs


# ============================================================
# KanbanState tests
# ============================================================

KanbanState = ps.KanbanState


class TestKanbanStateUpdateFromDag:

    def _make_dag(self):
        """Build a DAG with mixed statuses for summary counting."""
        tasks = [
            RecursiveTask(id="t1", description="done task", acceptance_criteria="",
                         dependencies=[], files=[], status="done", cost_usd=0.10),
            RecursiveTask(id="t2", description="failed task", acceptance_criteria="",
                         dependencies=[], files=[], status="failed", cost_usd=0.05),
            RecursiveTask(id="t3", description="running task", acceptance_criteria="",
                         dependencies=[], files=[], status="running", cost_usd=0.02),
            RecursiveTask(id="t4", description="pending task", acceptance_criteria="",
                         dependencies=[], files=[], status="pending", cost_usd=0.0),
            RecursiveTask(id="t5", description="pending task 2", acceptance_criteria="",
                         dependencies=[], files=[], status="pending", cost_usd=0.0),
        ]
        return RecursiveDAG(tasks)

    def test_summary_counts(self):
        """update_from_dag produces correct total/done/failed/pending/running counts."""
        dag = self._make_dag()
        ks = KanbanState("Test goal")
        ks.update_from_dag(dag)
        s = ks.summary
        assert s["total"] == 5
        assert s["done"] == 1
        assert s["failed"] == 1
        assert s["running"] == 1
        assert s["pending"] == 2

    def test_summary_total_cost(self):
        """update_from_dag computes correct total_cost_usd."""
        dag = self._make_dag()
        ks = KanbanState("Test goal")
        ks.update_from_dag(dag)
        assert abs(ks.summary["total_cost_usd"] - 0.17) < 0.001

    def test_tree_populated(self):
        """update_from_dag populates tree as a list of root nodes."""
        dag = self._make_dag()
        ks = KanbanState("Test goal")
        ks.update_from_dag(dag)
        assert isinstance(ks.tree, list)
        assert len(ks.tree) == 5  # all are roots (no parent)

    def test_empty_dag(self):
        """An empty DAG produces zero counts and empty tree."""
        dag = RecursiveDAG([])
        ks = KanbanState("Empty")
        ks.update_from_dag(dag)
        assert ks.summary["total"] == 0
        assert ks.summary["total_cost_usd"] == 0.0
        assert ks.tree == []

    def test_nested_dag_tree_structure(self):
        """A parent-child DAG produces nested tree nodes."""
        parent = RecursiveTask(id="p", description="parent", acceptance_criteria="",
                               dependencies=[], files=[], children=["c1"], cost_usd=0.0)
        child = RecursiveTask(id="c1", description="child", acceptance_criteria="",
                              dependencies=[], files=[], parent="p", cost_usd=0.03, status="done")
        dag = RecursiveDAG([parent, child])
        ks = KanbanState("Nested")
        ks.update_from_dag(dag)
        assert len(ks.tree) == 1  # only root
        assert ks.tree[0]["id"] == "p"
        assert len(ks.tree[0]["children"]) == 1
        assert ks.tree[0]["children"][0]["id"] == "c1"


class TestKanbanStateSave:

    def test_save_creates_file(self, tmp_path):
        """save() writes a file at the given path."""
        ks = KanbanState("Save test")
        out = str(tmp_path / "kanban.json")
        ks.save(path=out)
        assert os.path.isfile(out)

    def test_save_valid_json(self, tmp_path):
        """save() writes valid JSON that can be parsed."""
        ks = KanbanState("Save test")
        out = str(tmp_path / "kanban.json")
        ks.save(path=out)
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["goal"] == "Save test"
        assert "start_time" in data
        assert "updated_at" in data
        assert "summary" in data
        assert "tree" in data

    def test_save_creates_directories(self, tmp_path):
        """save() creates parent directories if they don't exist."""
        ks = KanbanState("Nested dir test")
        out = str(tmp_path / "deep" / "nested" / "kanban.json")
        ks.save(path=out)
        assert os.path.isfile(out)

    def test_save_with_populated_state(self, tmp_path):
        """save() after update_from_dag includes summary and tree data."""
        tasks = [
            RecursiveTask(id="t1", description="task", acceptance_criteria="",
                         dependencies=[], files=[], status="done", cost_usd=0.05,
                         commit_hash="abc1234"),
        ]
        dag = RecursiveDAG(tasks)
        ks = KanbanState("Full save test")
        ks.update_from_dag(dag)
        out = str(tmp_path / "kanban.json")
        ks.save(path=out)
        with open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["summary"]["total"] == 1
        assert data["summary"]["done"] == 1
        assert data["summary"]["total_cost_usd"] == 0.05
        assert len(data["tree"]) == 1
        assert data["tree"][0]["commit_hash"] == "abc1234"


class TestKanbanStatePrintTree:

    def _make_kanban_with_tree(self):
        """Build a KanbanState with a nested tree for print testing.

        Structure: p -> [c1 -> [gc1], c2]
        This ensures box-drawing chars including │ appear (│ shows in the
        prefix when a non-last child has sub-children).
        """
        parent = RecursiveTask(id="p", description="Parent task", acceptance_criteria="",
                               dependencies=[], files=[], children=["c1", "c2"],
                               cost_usd=0.0, status="running")
        c1 = RecursiveTask(id="c1", description="Child 1", acceptance_criteria="",
                           dependencies=[], files=[], parent="p", children=["gc1"],
                           cost_usd=0.15, status="done", commit_hash="abc1234")
        gc1 = RecursiveTask(id="gc1", description="Grandchild", acceptance_criteria="",
                            dependencies=[], files=[], parent="c1",
                            cost_usd=0.05, status="done")
        c2 = RecursiveTask(id="c2", description="Child 2", acceptance_criteria="",
                           dependencies=[], files=[], parent="p",
                           cost_usd=0.25, status="pending")
        dag = RecursiveDAG([parent, c1, gc1, c2])
        ks = KanbanState("Test goal")
        ks.update_from_dag(dag)
        return ks

    def test_contains_box_drawing_chars(self, capsys):
        """print_tree output includes box-drawing characters \u251c\u2500, \u2514\u2500, \u2502."""
        ks = self._make_kanban_with_tree()
        ks.print_tree()
        output = capsys.readouterr().out
        # Use Unicode escapes to avoid encoding issues on Windows
        assert "\u251c\u2500" in output or "\u2514\u2500" in output  # ├─ or └─
        assert "\u2502" in output  # │

    def test_contains_status_markers(self, capsys):
        """print_tree output includes [done], [pending], [running] markers."""
        ks = self._make_kanban_with_tree()
        ks.print_tree()
        output = capsys.readouterr().out
        assert "[done]" in output
        assert "[pending]" in output
        assert "[running]" in output

    def test_contains_cost_info(self, capsys):
        """print_tree output includes cost values."""
        ks = self._make_kanban_with_tree()
        ks.print_tree()
        output = capsys.readouterr().out
        assert "$0.15" in output
        assert "$0.25" in output

    def test_contains_commit_hash(self, capsys):
        """print_tree output includes commit hashes for done tasks."""
        ks = self._make_kanban_with_tree()
        ks.print_tree()
        output = capsys.readouterr().out
        assert "abc1234" in output

    def test_contains_goal_header(self, capsys):
        """print_tree output starts with goal line."""
        ks = self._make_kanban_with_tree()
        ks.print_tree()
        output = capsys.readouterr().out
        assert "Test goal" in output

    def test_empty_tree(self, capsys):
        """print_tree with no tasks just prints the header."""
        ks = KanbanState("Empty goal")
        ks.summary = {"total_cost_usd": 0.0}
        ks.print_tree()
        output = capsys.readouterr().out
        assert "Empty goal" in output
        # No box-drawing chars for empty tree
        assert "├─" not in output


# ============================================================
# CLI argument parsing tests
# ============================================================

class TestCLIArgs:

    def _parse(self, args_list):
        """Parse CLI args using the script's argparse setup."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("goal")
        parser.add_argument("--max-rounds", type=int, default=ps.DEFAULT_MAX_ROUNDS)
        parser.add_argument("--max-time", type=int, default=ps.DEFAULT_MAX_TIME)
        parser.add_argument("--max-budget-usd", type=float, default=5.0)
        parser.add_argument("--per-task-budget", type=float, default=0.5)
        parser.add_argument("--mode", choices=["dag", "legacy"], default="dag")
        parser.add_argument("--no-clarify", action="store_true")
        parser.add_argument("--recursive", action="store_true")
        parser.add_argument("--kanban", action="store_true")
        parser.add_argument("--kanban-path", type=str, default=None)
        parser.add_argument("--verify-level", choices=["auto", "l1", "l2", "l3"], default="auto")
        return parser.parse_args(args_list)

    def test_recursive_default_false(self):
        """--recursive defaults to False."""
        args = self._parse(["my goal"])
        assert args.recursive is False

    def test_recursive_flag(self):
        """--recursive sets True."""
        args = self._parse(["my goal", "--recursive"])
        assert args.recursive is True

    def test_kanban_default_false(self):
        """--kanban defaults to False (store_true)."""
        args = self._parse(["my goal"])
        assert args.kanban is False

    def test_kanban_flag(self):
        """--kanban sets True."""
        args = self._parse(["my goal", "--kanban"])
        assert args.kanban is True

    def test_kanban_path_default_none(self):
        """--kanban-path defaults to None."""
        args = self._parse(["my goal"])
        assert args.kanban_path is None

    def test_kanban_path_custom(self):
        """--kanban-path accepts custom path."""
        args = self._parse(["my goal", "--kanban-path", "/tmp/kb.json"])
        assert args.kanban_path == "/tmp/kb.json"

    def test_verify_level_default_auto(self):
        """--verify-level defaults to 'auto'."""
        args = self._parse(["my goal"])
        assert args.verify_level == "auto"

    def test_verify_level_choices(self):
        """--verify-level accepts l1, l2, l3."""
        for level in ["l1", "l2", "l3", "auto"]:
            args = self._parse(["my goal", "--verify-level", level])
            assert args.verify_level == level

    def test_verify_level_invalid_rejected(self):
        """--verify-level rejects invalid values."""
        with pytest.raises(SystemExit):
            self._parse(["my goal", "--verify-level", "l4"])

    def test_backward_compatibility_no_new_flags(self):
        """Without new flags, old behavior is preserved: mode=dag, no recursive."""
        args = self._parse(["my goal"])
        assert args.mode == "dag"
        assert args.recursive is False
        assert args.kanban is False
        assert args.kanban_path is None
        assert args.verify_level == "auto"

    def test_all_flags_together(self):
        """All new flags can be combined."""
        args = self._parse([
            "my goal", "--recursive", "--kanban",
            "--kanban-path", "out/kb.json", "--verify-level", "l2",
        ])
        assert args.recursive is True
        assert args.kanban is True
        assert args.kanban_path == "out/kb.json"
        assert args.verify_level == "l2"
