#!/usr/bin/env bash
# =============================================================================
# persistent-solve v2 升级脚本 — 分 4 阶段自举执行
#
# 用法:
#   bash scripts/run-v2-upgrade.sh           # 从阶段 1 开始
#   bash scripts/run-v2-upgrade.sh 3         # 从阶段 3 开始（前两阶段已完成）
#
# 每个阶段完成后暂停，让用户检查 git log / 测试结果，确认后继续。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

PLAN_FILE="Docs/persistent-solve-v2/plan.md"
START_PHASE="${1:-1}"
BUDGET_PER_PHASE=5.0
BUDGET_PER_TASK=1.0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[v2-upgrade]${NC} $*"; }
ok()   { echo -e "${GREEN}[v2-upgrade]${NC} $*"; }
warn() { echo -e "${YELLOW}[v2-upgrade]${NC} $*"; }
fail() { echo -e "${RED}[v2-upgrade]${NC} $*"; exit 1; }

# Pre-flight checks
[[ -f "$PLAN_FILE" ]] || fail "Plan file not found: $PLAN_FILE"
command -v claude >/dev/null 2>&1 || fail "'claude' not in PATH"
command -v python >/dev/null 2>&1 || fail "'python' not in PATH"

# Tag the starting point for easy rollback
START_TAG="v2-upgrade-start-$(date +%Y%m%d-%H%M%S)"
git tag "$START_TAG" 2>/dev/null || true
log "Tagged starting point: $START_TAG"
log "To rollback everything: git revert --no-commit ${START_TAG}..HEAD"

# =============================================================================
# Gate: pause between phases
# =============================================================================
gate() {
    local phase="$1"
    local next="$2"
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Phase $phase COMPLETE${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    log "Review the changes:"
    log "  git log --oneline ${START_TAG}..HEAD"
    log "  python -m pytest tests/test_persistent_solve.py -v"
    echo ""

    if [[ "$next" -le 4 ]]; then
        if [[ "${AUTO_CONFIRM:-}" == "1" ]]; then
            log "AUTO_CONFIRM=1, continuing to Phase $next..."
        else
            read -r -p "$(echo -e "${YELLOW}Continue to Phase $next? [Y/n/q] ${NC}")" choice
            case "${choice,,}" in
                n|q) log "Stopped at Phase $phase. Resume with: bash scripts/run-v2-upgrade.sh $next"; exit 0 ;;
                *)   log "Continuing to Phase $next..." ;;
            esac
        fi
    fi
}

# =============================================================================
# Phase 1: Data Model (RecursiveTask + RecursiveDAG + tests)
# =============================================================================
run_phase_1() {
    log "Phase 1/4: Data Model Layer"
    log "Goal: RecursiveTask, RecursiveDAG, propagate_status, to_kanban_dict"

    python scripts/persistent-solve.py \
"Rewrite the data model layer in scripts/persistent-solve.py. Read Docs/persistent-solve-v2/plan.md first for full context.

## What to do

1. KEEP these existing classes/functions UNCHANGED:
   - BudgetTracker (entire class)
   - clarify_goal, build_clarify_prompt, build_plan_prompt
   - run_claude_session, _parse_claude_json
   - WIP file operations (ensure_wip_dir, read_wip, parse_wip_status, count_completed_tasks, delete_wip)
   - WIP_INSTRUCTIONS, build_first_round_prompt, build_resume_prompt
   - _run_legacy_mode (entire function)
   - main() CLI entry point

2. REPLACE Task dataclass with RecursiveTask:
   - Add fields: complexity (int, 1-5), depth (int), children (list[str]), parent (str|None), cost_usd (float), commit_hash (str|None), error_summary (str|None)
   - Keep existing fields: id, description, acceptance_criteria, dependencies, files, status, retries, max_retries

3. REPLACE TaskDAG with RecursiveDAG:
   - Keep: get_ready_tasks (rename to get_ready_leaves, only returns leaf nodes), get_parallel_groups, mark_done, all_done, summary
   - Change mark_failed: unconditionally set status='failed', NO retry logic inside (retry is owned by execution layer)
   - Add: get_leaf_tasks(), get_children(task_id), get_subtree(task_id), replace_subtree(task_id, new_children), propagate_status() with threading lock, to_kanban_dict()
   - propagate_status: when all children of a parent are 'done', mark parent 'done'. Use threading.Lock to prevent duplicate triggers.
   - replace_subtree: replace a task's children with new tasks, remap downstream dependencies from old IDs to new root ID

4. REWRITE tests/test_persistent_solve.py:
   - Update all existing tests to use RecursiveTask/RecursiveDAG
   - Add tests for: get_leaf_tasks, get_subtree, propagate_status (children all done -> parent done), replace_subtree (downstream dep remapping), to_kanban_dict, mark_failed (unconditional, no retry)
   - Keep existing BudgetTracker and clarify_goal tests unchanged

5. Run pytest to verify all tests pass.

## Constraints
- Python standard library only (no pip packages)
- Single file: scripts/persistent-solve.py
- Do NOT touch _run_legacy_mode or _run_dag_mode yet (they will be updated in Phase 3)" \
        --max-budget-usd "$BUDGET_PER_PHASE" \
        --per-task-budget "$BUDGET_PER_TASK" \
        --no-clarify

    gate 1 2
}

# =============================================================================
# Phase 2: Planning Layer (recursive decomposition + contracts)
# =============================================================================
run_phase_2() {
    log "Phase 2/4: Planning Layer"
    log "Goal: recursive_plan, parse_recursive_dag_response, Contract, PlanningError"

    python scripts/persistent-solve.py \
"Add the recursive planning layer to scripts/persistent-solve.py. Read Docs/persistent-solve-v2/plan.md first (sections 4.2, 5.2, 5.3).

## What to do

1. Add PlanningError exception class.

2. Add build_recursive_plan_prompt(goal, depth, parent_contract=None):
   - Similar to existing build_plan_prompt but requires 'complexity' field (1-5) in output JSON
   - If parent_contract is provided, include it in the prompt as context
   - Prompt must instruct Claude to output JSON array with: id, description, acceptance_criteria, dependencies, files, complexity

3. Add parse_recursive_dag_response(response, parent_id=None):
   - Parse JSON from response (look for \`\`\`json fence)
   - Validate each task's complexity is int in [1, 5] — if not, raise PlanningError
   - If JSON parse fails entirely, raise PlanningError (do NOT create fallback single-task)
   - If parent_id is provided, prefix all task IDs with '{parent_id}.' to ensure global uniqueness
   - Also remap dependencies to use prefixed IDs
   - Return list of RecursiveTask objects

4. Add recursive_plan(goal, budget, depth=0, parent_id=None) -> RecursiveDAG:
   - Call Claude via run_claude_session with build_recursive_plan_prompt
   - Parse response with parse_recursive_dag_response
   - For each task with complexity >= 3: recurse (call recursive_plan with task as sub-goal)
   - Hard limit: if depth > 5 (MAX_RECURSION_DEPTH), force task as leaf regardless of complexity
   - Generate contract file for each non-leaf task
   - Return RecursiveDAG with all tasks (flattened across all depths)

5. Add Contract dataclass:
   - Fields: dag_id, inputs, outputs, constraints
   - to_markdown() -> str
   - save(base_dir='.claude-flow/contracts')
   - load(path) -> Contract (static method)
   - Contract generation: call Claude to analyze task description and produce inputs/outputs/constraints

6. Add helper functions:
   - load_relevant_contracts(task, dag) -> str: load parent + completed sibling contracts, return as markdown
   - cleanup_contracts(base_dir): delete all contract files

7. Add tests in tests/test_persistent_solve.py for:
   - parse_recursive_dag_response: valid JSON with complexity
   - parse_recursive_dag_response: complexity out of [1,5] -> PlanningError
   - parse_recursive_dag_response: malformed JSON -> PlanningError (no fallback)
   - parse_recursive_dag_response: ID prefixing with parent_id
   - build_recursive_plan_prompt: contains complexity requirement
   - Contract: to_markdown and save/load roundtrip

8. Run pytest to verify.

## Constraints
- Python standard library only
- MAX_RECURSION_DEPTH = 5 (module-level constant)
- Keep all existing functions intact" \
        --max-budget-usd "$BUDGET_PER_PHASE" \
        --per-task-budget "$BUDGET_PER_TASK" \
        --no-clarify

    gate 2 3
}

# =============================================================================
# Phase 3: Execution Layer (recursive execute + verify + replan)
# =============================================================================
run_phase_3() {
    log "Phase 3/4: Execution Layer"
    log "Goal: execute_recursive_dag, verification, replan_subtree, checkpoint_commit"

    python scripts/persistent-solve.py \
"Add the recursive execution layer to scripts/persistent-solve.py. Read Docs/persistent-solve-v2/plan.md first (sections 4.1, 4.3, 4.4, 5.4).

## What to do

1. Add execute_recursive_dag(dag, goal, budget, kanban=None):
   - Main loop: while dag.get_ready_leaves() and budget.can_afford()
   - Get ready leaves, split into parallel/sequential groups
   - Execute parallel leaves via ThreadPoolExecutor
   - Execute sequential leaves one by one
   - After each leaf: L1 verification (check acceptance criteria via Claude)
   - After each leaf: checkpoint_commit (git commit)
   - After each batch: dag.propagate_status()
   - When a branch (non-leaf parent) becomes 'done': run verification based on complexity
     - C:3-4 -> run_l2 (adversarial review via Claude)
     - C:5 -> run_l2 + run_l3 (end-to-end test suite)
   - Update kanban after each batch if kanban is provided
   - Failure handling (execution layer owns retry count):
     - Maintain dict execution_retries = {}
     - On task failure: increment execution_retries[task.id]
     - If retries < task.max_retries: set task.status = 'pending' (retry)
     - If retries >= max: dag.mark_failed(task.id, error) then replan_subtree
     - If replan also fails: mark [FAILED], continue other branches

2. Add execute_leaf_task(task, goal, budget, contracts_text=''):
   - Build prompt with: goal context + task description + acceptance criteria + contract injection
   - Call run_claude_session
   - Return result dict

3. Add checkpoint_commit(task, success) -> str:
   - On success: git commit -m 'checkpoint: {task.id} {task.description}'
   - On failure: git commit -m '[FAILED] checkpoint: {task.id} {task.description}'
   - Return commit hash (from git rev-parse HEAD)
   - Handle case where there are no changes to commit (return None)

4. Add run_l1(task, budget) -> bool:
   - Quick self-check: call Claude to verify acceptance criteria against current code
   - Return True/False

5. Add run_l2(task, budget) -> bool:
   - Adversarial review: call Claude as strict reviewer on git diff
   - If issues found: call Claude as executor to fix
   - Max 2 rounds of review-fix loop
   - Return True if PASS, False if issues remain

6. Add run_l3(task, budget) -> bool:
   - Run full test suite (python -m pytest)
   - Return True if all pass

7. Add replan_subtree(task, dag, error_context, budget) -> bool:
   - Collect failure context + sibling contracts
   - Call Claude to re-decompose the failed task
   - Parse new sub-tasks
   - dag.replace_subtree(task.id, new_children) — this also cleans old contracts and remaps deps
   - Generate new contracts for new sub-tasks
   - Return True if replan succeeded, False if it also failed

8. REPLACE the existing _run_dag_mode function:
   - Phase 0: clarify_goal (keep existing)
   - Phase 1: if --recursive flag, use recursive_plan(); else use plan_dag() (existing)
   - Phase 2: if --recursive, use execute_recursive_dag(); else use execute_dag() (existing)
   - Phase 3: finalize (cleanup contracts, print summary)

9. Add tests for:
   - checkpoint_commit: success vs failure commit messages (mock subprocess)
   - run_verification dispatching: C:1->L1, C:3->L1+L2, C:5->L1+L2+L3
   - execute_leaf_task: prompt contains contract text when provided
   - execute_leaf_task: prompt works without contracts

10. Run pytest to verify.

## Constraints
- Python standard library only
- Keep _run_legacy_mode unchanged
- Keep backward compatibility: without --recursive, behavior is same as v1" \
        --max-budget-usd "$BUDGET_PER_PHASE" \
        --per-task-budget "$BUDGET_PER_TASK" \
        --no-clarify

    gate 3 4
}

# =============================================================================
# Phase 4: Kanban + CLI + Docs
# =============================================================================
run_phase_4() {
    log "Phase 4/4: Kanban + CLI + Docs"
    log "Goal: KanbanState, CLI args, README, docs"

    python scripts/persistent-solve.py \
"Add the kanban layer and update CLI in scripts/persistent-solve.py. Read Docs/persistent-solve-v2/plan.md first (sections 5.5, 5.6).

## What to do

1. Add KanbanState class:
   - __init__(self, goal: str): set goal, start_time, tree={}, summary={}
   - update_from_dag(self, dag: RecursiveDAG): rebuild tree structure from dag.to_kanban_dict(), compute summary (total/done/failed/pending/running/total_cost_usd)
   - save(self, path='.claude-flow/kanban.json'): write JSON to file (create dirs if needed)
   - print_tree(self): print tree to terminal with indentation, using box-drawing chars:
     Format per node: [status] id: description  (\$cost)  commit_hash
     Example:
       [running] Root goal  (\$2.34)
       ├─ [done] T1: Setup  (\$0.40)  abc1234
       │  ├─ [done] T1.1: Subtask  (\$0.15)  def5678
       │  └─ [done] T1.2: Subtask  (\$0.25)  ghi9012
       ├─ [running] T2: Core logic  (\$0.80)
       └─ [pending] T3: Tests

2. Update main() CLI:
   - Add --recursive flag (store_true, default=False): enable recursive DAG decomposition
   - Add --kanban flag (store_true, default=True): enable kanban output
   - Add --kanban-path (default='.claude-flow/kanban.json'): kanban JSON output path
   - Add --verify-level (choices=['auto','l1','l2','l3'], default='auto'): verification level override
   - Pass these to persistent_solve() and _run_dag_mode()
   - Ensure backward compatibility: without --recursive, uses original flat DAG behavior

3. Update persistent_solve() signature to accept new args.

4. Add tests:
   - KanbanState.update_from_dag: correct summary counts
   - KanbanState.save: writes valid JSON
   - KanbanState.print_tree: output contains expected tree chars
   - CLI: new args parse correctly
   - CLI: default values backward compatible

5. Update README.md:
   - Add new CLI parameters to the persistent-solve section
   - Add description of recursive DAG feature
   - Add kanban.json output description

6. Update Docs/persistent-loop.md:
   - Document recursive mode
   - Document kanban output format
   - Document verification levels

7. Run pytest to verify all tests pass.

## Constraints
- Python standard library only
- Do NOT break existing CLI usage" \
        --max-budget-usd 3.0 \
        --per-task-budget "$BUDGET_PER_TASK" \
        --no-clarify

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ALL 4 PHASES COMPLETE${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    log "Review full diff: git diff ${START_TAG}..HEAD"
    log "Run tests: python -m pytest tests/test_persistent_solve.py -v"
    log "To rollback everything: git revert --no-commit ${START_TAG}..HEAD"
}

# =============================================================================
# Main: run from specified phase
# =============================================================================
log "Starting v2 upgrade from Phase $START_PHASE"
log "Plan: $PLAN_FILE"
log "Budget: \$${BUDGET_PER_PHASE}/phase, \$${BUDGET_PER_TASK}/task"
echo ""

for phase in $(seq "$START_PHASE" 4); do
    "run_phase_$phase"
done
