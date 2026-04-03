# Contract: task-2.task-2

## Inputs
- _run_dag_mode receives a new parameter `dry_run: bool = False`
- `goal: str` — the user's goal text, used to initialize KanbanState
- `budget: BudgetTracker` — passed to plan_dag/recursive_plan for Phase 1 planning
- `recursive: bool` — selects between recursive_plan() and plan_dag() for DAG generation
- `kanban_path: str | None` — optional explicit output path; defaults to WIP_DIR/kanban.json
- Phase 1 planning output: `dag: RecursiveDAG` with `.tasks` dict and `.to_kanban_dict()` method
- `KanbanState` class with `__init__(goal)`, `update_from_dag(dag)`, `save(path)`, `print_tree()` methods

## Outputs
- KanbanState is always created when dry_run=True (regardless of --kanban flag)
- kanban JSON file written to kanban_out path via KanbanState.save()
- Task tree printed to stdout via KanbanState.print_tree()
- Function returns after first planning round — execute_recursive_dag and execute_dag are never called
- Process exits with code 0 (normal return, no sys.exit(1))

## Constraints
- dry_run=True forces KanbanState creation even when kanban=False; kanban_out defaults to WIP_DIR/kanban.json
- Only Phase 1 (planning) executes; Phase 2 (execute_dag / execute_recursive_dag) must be skipped entirely
- The early return must happen after the first planning round — the for-loop body runs exactly once
- update_from_dag, save, and print_tree must be called in that order before returning
- No changes to KanbanState, plan_dag, recursive_plan, or execute_* function signatures
- If dag.tasks is empty after planning, the existing 'No tasks generated' print + break behavior should still apply before the dry-run return path
- scripts/ must use only Python standard library (Constitution §3)
