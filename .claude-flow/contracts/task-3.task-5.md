# Contract: task-3.task-5

## Inputs
- scripts/task-stats.py module exposing: load_kanban(target_dir), extract_stats(kanban), format_oneline(stats), main()
- kanban.json schema: {goal, start_time, updated_at, summary: {total, done, failed, running, pending, total_cost_usd}, tree}
- pytest framework with tmp_path and capsys fixtures
- importlib for loading hyphenated module name

## Outputs
- tests/test_task_stats.py with passing pytest suite covering: valid text output, valid JSON output, missing file error (non-zero exit + stderr message), malformed JSON error, case-insensitive status counting, missing/null cost handling, empty tree, mixed statuses

## Constraints
- Zero external dependencies — only stdlib + pytest (Constitution §3)
- Tests must use tmp_path fixture for filesystem isolation, not modify real .claude-flow/kanban.json
- Module import via importlib (filename contains hyphen)
- sys.argv must be saved/restored around main() calls to avoid test pollution
- Acceptance requires all tests passing under pytest
- Must cover all six acceptance-criteria paths: valid text, valid JSON, missing file, malformed JSON, case-insensitive status, missing/null cost
