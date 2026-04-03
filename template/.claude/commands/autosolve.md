---
description: Launch persistent shell scheduler with kanban board
argument-hint: <goal description>
---

# /autosolve

Launch the persistent shell scheduler (`persistent-solve.py`) in recursive DAG mode with kanban visualization.

## Execution

Run the following command in the terminal via `!` prefix (this must run in the user's shell, not inside Claude):

```
! python scripts/persistent-solve.py "$ARGUMENTS" --recursive --kanban-serve
```

**Do NOT execute this command yourself.** Output the exact command for the user to run:

```
To start the scheduler with kanban board, run:

! python scripts/persistent-solve.py "<goal>" --recursive --kanban-serve
```

Replace `<goal>` with the user's $ARGUMENTS.

## What this does

1. Decomposes the goal into a recursive DAG of sub-tasks
2. Executes sub-tasks atomically via `claude -p` with budget tracking
3. Writes real-time progress to `.claude-flow/kanban.json`
4. Starts an HTTP server on port 8420 and opens `kanban-viewer.html` in the browser
5. The kanban board auto-refreshes every 3 seconds

## Optional flags the user can append

| Flag | Description |
|------|-------------|
| `--max-budget-usd N` | Total budget cap (default: 5.0) |
| `--per-task-budget N` | Per sub-task budget (default: 0.5) |
| `--max-rounds N` | Max execution rounds (default: 10) |
| `--max-time N` | Max time in seconds (default: 7200) |
| `--kanban-port N` | HTTP server port (default: 8420) |
| `--dry-run` | Only plan, print kanban tree, don't execute |
| `--no-clarify` | Skip goal clarification, go straight to planning |
