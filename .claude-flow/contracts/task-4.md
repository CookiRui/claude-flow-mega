# Contract: task-4

## Inputs
- scripts/task-stats.py module exposing: load_kanban(target_dir), extract_stats(kanban), format_oneline(stats), main()
- .claude-flow/kanban.json schema: {goal, start_time, updated_at, summary: {total, done, failed, running, pending, total_cost_usd}, tree}
- pytest framework with tmp_path and capsys fixtures

## Outputs
- tests/test_task_stats.py — pytest test suite covering 5 test classes: TestDefaultOutput, TestJsonOutput, TestMissingKanban, TestEmptyTree, TestMixedStatuses
- Validates text output contains all summary fields (total, done, failed, pending, cost)
- Validates --json output is parseable JSON with correct keys and values
- Validates missing kanban.json triggers non-zero exit and stderr error message
- Validates empty tree with zero counts produces valid output without exceptions

## Constraints
- Python standard library only — no external test dependencies beyond pytest (Constitution §3)
- Import scripts/task-stats.py via importlib due to hyphenated filename
- Tests must manipulate sys.argv to simulate CLI invocation and restore it in finally blocks
- Use tmp_path fixture for isolated filesystem — write kanban.json via helper, never touch real project files
- Missing-file tests must assert SystemExit with non-zero code (cli-tools Rule 2: fail-fast with non-zero exit)
- Error messages must reference kanban.json or 'not found' on stderr (cli-tools Rule 4: error messages are documentation)
