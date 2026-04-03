# Contract: task-3.task-3.write-test

## Inputs
- ps.recursive_plan(goal, budget) -> RecursiveDAG with dict-keyed .tasks attribute
- ps.execute_recursive_dag(dag, goal, budget, kanban_state, kanban_path) — function to be patched and verified NOT called
- ps._run_dag_mode(goal, max_rounds, max_time, budget, start_time, skip_clarify, recursive, kanban, kanban_path, verify_level, dry_run) — 6 required positional args: goal, max_rounds, max_time, budget, start_time
- ps.BudgetTracker(max_dollars=float) — budget tracker instance
- ps.RecursiveDAG(tasks=[RecursiveTask(...)]) — DAG with .tasks dict and .summary() method
- ps.RecursiveTask(id, description, acceptance_criteria, dependencies, files) — task dataclass
- Existing TestDryRun class and synthetic_dag fixture in tests/test_dry_run.py

## Outputs
- test_recursive_dry_run_skips_execution method in TestDryRun class
- Assertion: recursive_plan called at least once (call_count >= 1)
- Assertion: execute_recursive_dag.call_count == 0
- Assertion: kanban JSON file exists on disk after dry_run completes

## Constraints
- _run_dag_mode requires positional args (goal, max_rounds, max_time, budget, start_time) — cannot omit them as in existing test
- recursive_plan must return a RecursiveDAG whose .tasks is a dict (keyed by task id), not a list
- Must pass dry_run=True, recursive=True, skip_clarify=True, kanban=True to _run_dag_mode
- kanban_path must point to a real writable path (use tmp_path fixture) so kanban JSON file existence can be asserted
- Must patch ps.recursive_plan (not ps.plan_dag) since recursive=True triggers the recursive branch
- Must patch ps.execute_recursive_dag (not ps.execute_dag) since recursive=True uses the recursive executor
- start_time must be a valid float (e.g., time.time()) to avoid arithmetic errors in elapsed-time check
- max_rounds >= 1 and max_time large enough that the circuit breaker doesn't abort before planning
