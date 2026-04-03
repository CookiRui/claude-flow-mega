# Contract: task-3.task-2.task-2.task-2

## Inputs
- scripts/persistent-solve.py module loadable via importlib (hyphenated filename)
- RecursiveTask dataclass: id, description, acceptance_criteria, dependencies, files, status
- RecursiveDAG class: constructor accepts list[RecursiveTask], exposes to_kanban_dict()
- BudgetTracker class: constructor(max_budget_usd, per_task_budget_usd)
- KanbanState class: update_from_dag(dag), save(path)
- _run_dag_mode(goal, max_rounds, max_time, budget, start_time, skip_clarify, recursive, kanban, kanban_path, verify_level, dry_run)
- plan_dag(goal, budget) -> RecursiveDAG
- execute_dag(dag, goal, budget, kanban_state, kanban_path) -> None
- clarify_goal(goal, budget) -> str

## Outputs
- tests/test_dry_run.py: pytest-discoverable test module
- Assertion: plan_dag.called == True when dry_run=True
- Assertion: execute_dag.call_count == 0 when dry_run=True
- Assertion: kanban.json contains valid JSON when kanban=True and dry_run=True
- Synthetic DAG fixture with at least one RecursiveTask and dependency chain

## Constraints
- Module loading must use importlib.import_module due to hyphenated filename persistent-solve.py
- sys.path must be patched to include scripts/ directory before import
- All three functions (plan_dag, execute_dag, clarify_goal) must be mocked via @patch.object(ps, ...)
- plan_dag mock must return a valid RecursiveDAG (not a plain dict)
- File I/O tests must use tempfile directories to avoid polluting the repo
- Zero external dependencies — only stdlib + pytest (per Constitution §3)
- BudgetTracker must use max_budget_usd kwarg (not max_dollars)
- _run_dag_mode requires all 5 positional args: goal, max_rounds, max_time, budget, start_time
- kanban JSON validation must parse the file and check structure (summary + tree keys)
- Tests must not invoke real subprocess/Claude API calls
