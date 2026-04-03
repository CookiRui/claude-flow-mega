# Contract: task-2

## Inputs
- CLI flag --dry-run (argparse boolean, propagated through persistent_solve → _run_dag_mode as `dry_run: bool` parameter)
- RecursiveDAG returned by recursive_plan(goal, budget) or plan_dag(goal, budget) — must have .tasks dict and .to_kanban_dict() method
- KanbanState class — requires goal string for __init__, and exposes update_from_dag(dag), print_tree(), save(path) methods
- kanban_path (str or None) — resolved to kanban_out inside _run_dag_mode, defaults to .claude-flow/kanban.json when --kanban is set
- BudgetTracker instance — consumed by recursive_plan/plan_dag during planning phase (planning still costs budget even in dry-run)

## Outputs
- Kanban JSON file written to kanban_out path via kanban_state.save() containing goal, tree, summary, and timestamps
- Terminal tree-view printed to stdout via kanban_state.print_tree() showing all planned tasks with status/id/description/cost
- Process exits with code 0 after printing — no task execution side effects (no claude -p calls, no commits, no file modifications beyond kanban JSON)

## Constraints
- When --dry-run is active, execute_recursive_dag and execute_dag must NOT be called — the for-loop must return/break after Phase 1 (planning) on the first iteration
- KanbanState must be initialized and populated even when --kanban flag is not explicitly set — dry-run implies kanban output so the tree can be printed
- kanban_state.update_from_dag(dag) must be called before print_tree/save, since KanbanState starts with empty tree/summary
- The --dry-run flag must propagate through 3 layers: main() argparse → persistent_solve() → _run_dag_mode() without being silently defaulted (per cli-tools Rule 1)
- Budget is still consumed during the planning phase (recursive_plan/plan_dag call Claude API) — dry-run only skips execution, not planning
- Only one planning round is needed — dry-run should plan once and exit, not loop through max_rounds
- Python standard library only — no external dependencies (per constitution §3)
