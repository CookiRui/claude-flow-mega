# Contract: task-3

## Inputs
- .claude-flow/kanban.json — JSON file containing task objects with at least 'status' and 'cost' fields
- CLI arguments via argparse: optional --json flag, optional --file to override kanban path

## Outputs
- stdout text mode: one-line summary e.g. 'Total: 10 | Done: 5 | Failed: 1 | Pending: 4 | Cost: $1.23'
- stdout JSON mode (--json): valid JSON object with fields {total, done, failed, pending, cost}
- exit code 0 on success, non-zero on error (e.g. missing/invalid kanban file)

## Constraints
- Python stdlib only — no external dependencies (Constitution §3)
- argparse for CLI interface with standard entry point pattern (if __name__ == '__main__': main())
- Fail-fast with non-zero exit and descriptive error message if kanban file missing or malformed (cli-tools Rule 2, 4)
- JSON output with 'success': false must accompany exit code 1 (cli-tools Rule 3)
- Status field values must be parsed case-insensitively to count done/failed/pending buckets
- Cost aggregation must handle missing or null cost fields gracefully (default to 0)
