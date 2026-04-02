#!/usr/bin/env python3
"""
Persistent Loop Scheduler — Atomic DAG execution with budget tracking.

Usage:
    # DAG mode (default): plan sub-tasks, execute each atomically with budget control
    python scripts/persistent-solve.py "Stabilize game frame rate at 60fps"
    python scripts/persistent-solve.py "Refactor auth system" --max-budget-usd 3.0 --per-task-budget 0.3

    # Legacy mode: original WIP-handshake loop (one full session per round)
    python scripts/persistent-solve.py "Fix memory leak" --mode legacy

    # Common options
    python scripts/persistent-solve.py "Goal" --max-rounds 5 --max-time 1800

DAG mode (default):
    1. Calls Claude to decompose the goal into a DAG of sub-tasks (JSON)
    2. Executes each sub-task as an independent `claude -p` call
    3. Non-conflicting tasks run in parallel (process-level)
    4. Tracks token usage and cost per task via --output-format json
    5. Circuit breakers: total budget, per-task budget, time, rounds

Legacy mode:
    1. Launches a full Claude Code session per round
    2. Claude saves progress to .claude-flow/wip.md before budget runs out
    3. Script reads WIP file, injects it into next session's prompt
    4. Repeats until goal achieved or circuit breaker triggers
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ============================================================
# Constants
# ============================================================
DEFAULT_MAX_ROUNDS = 10
DEFAULT_MAX_TIME = 7200      # 2 hours
MAX_CONSECUTIVE_NO_PROGRESS = 3
WIP_DIR = ".claude-flow"
WIP_FILE = f"{WIP_DIR}/wip.md"


# ============================================================
# DAG Data Structures
# ============================================================

@dataclass
class RecursiveTask:
    """A single sub-task in the recursive DAG."""
    id: str
    description: str
    acceptance_criteria: str
    dependencies: list  # list of task IDs
    files: list  # files to modify
    status: str = "pending"  # pending | running | done | failed
    result: dict = None  # result from claude session
    retries: int = 0
    max_retries: int = 2
    complexity: int = 1  # 1-5 complexity rating
    depth: int = 0  # depth in task tree
    children: list = None  # list of child task IDs
    parent: str = None  # parent task ID or None
    cost_usd: float = 0.0  # cost tracking
    commit_hash: str = None  # git commit hash when done
    error_summary: str = None  # summary of last error

    def __post_init__(self):
        if self.children is None:
            self.children = []

class RecursiveDAG:
    """Directed Acyclic Graph of tasks with dependency tracking and tree structure."""

    def __init__(self, tasks: list[RecursiveTask] = None):
        self.tasks = {t.id: t for t in (tasks or [])}
        self._lock = threading.Lock()

    def add_task(self, task: RecursiveTask):
        self.tasks[task.id] = task

    def get_leaf_tasks(self) -> list[RecursiveTask]:
        """Return all tasks that have no children (leaf nodes)."""
        return [t for t in self.tasks.values() if not t.children]

    def get_children(self, task_id: str) -> list[RecursiveTask]:
        """Return direct children of a task."""
        task = self.tasks.get(task_id)
        if not task or not task.children:
            return []
        return [self.tasks[cid] for cid in task.children if cid in self.tasks]

    def get_subtree(self, task_id: str) -> list[RecursiveTask]:
        """Return a task and all its descendants recursively."""
        task = self.tasks.get(task_id)
        if not task:
            return []
        result = [task]
        for child_id in task.children:
            result.extend(self.get_subtree(child_id))
        return result

    def get_ready_leaves(self) -> list[RecursiveTask]:
        """Get leaf tasks whose dependencies are all done."""
        ready = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue
            if task.children:
                continue  # only leaf nodes
            deps_met = all(
                self.tasks[dep].status == "done"
                for dep in task.dependencies
                if dep in self.tasks
            )
            if deps_met:
                ready.append(task)
        return ready

    def get_parallel_groups(self, ready: list[RecursiveTask]) -> tuple[list[RecursiveTask], list[RecursiveTask]]:
        """Split ready tasks into parallel (no file conflicts) and sequential groups.

        Tasks with empty ``files`` lists are treated as potentially conflicting
        and placed in the sequential group (since we don't know what they touch).
        """
        if len(ready) <= 1:
            return ready, []

        parallel = []
        sequential = []
        used_files: set = set()

        for task in ready:
            if not task.files:
                # Unknown file scope — run sequentially to be safe
                sequential.append(task)
            elif set(task.files) & used_files:
                sequential.append(task)
            else:
                parallel.append(task)
                used_files |= set(task.files)

        # If nothing qualified for parallel, run the first sequentially
        if not parallel and sequential:
            parallel = [sequential.pop(0)]

        return parallel, sequential

    def mark_done(self, task_id: str, result: dict = None):
        if task_id in self.tasks:
            self.tasks[task_id].status = "done"
            self.tasks[task_id].result = result

    def mark_failed(self, task_id: str, error_summary: str = None, result: dict = None):
        """Unconditionally set task status to 'failed'. Retry logic is owned by execution layer."""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task.status = "failed"
            task.error_summary = error_summary
            task.result = result

    def propagate_status(self):
        """When all children of a parent are done, mark parent done.

        Uses threading.Lock to prevent duplicate triggers when multiple
        children complete concurrently. Handles multi-level propagation
        by walking up the parent chain.
        """
        with self._lock:
            changed = True
            while changed:
                changed = False
                for task in self.tasks.values():
                    if task.status == "done" or not task.children:
                        continue
                    children = [self.tasks[cid] for cid in task.children if cid in self.tasks]
                    if children and all(c.status == "done" for c in children):
                        task.status = "done"
                        changed = True

    def has_ready_tasks(self) -> bool:
        return len(self.get_ready_leaves()) > 0

    def all_done(self) -> bool:
        return all(t.status in ("done", "failed") for t in self.tasks.values())

    def summary(self) -> str:
        lines = []
        for t in self.tasks.values():
            cost = f" ${t.result.get('cost_usd', 0):.4f}" if t.result else ""
            lines.append(f"  {t.id}: [{t.status}] {t.description}{cost}")
        return "\n".join(lines)


# ============================================================
# Budget Tracker
# ============================================================

class BudgetTracker:
    """Track cumulative costs across all claude sessions (thread-safe)."""

    def __init__(self, max_budget_usd: float = 5.0, per_task_budget_usd: float = 0.5):
        self.max_budget = max_budget_usd
        self.per_task_budget = per_task_budget_usd
        self.total_spent = 0.0
        self.task_costs = {}  # task_id -> cost
        self._lock = threading.Lock()

    def record(self, task_id: str, cost_usd: float):
        """Record cost for a task (thread-safe)."""
        with self._lock:
            self.total_spent += cost_usd
            self.task_costs[task_id] = self.task_costs.get(task_id, 0) + cost_usd

    def remaining(self) -> float:
        """Return remaining budget."""
        return max(0, self.max_budget - self.total_spent)

    def can_afford(self, estimated_cost: float = None) -> bool:
        """Check if we can afford another task."""
        if self.remaining() <= 0:
            return False
        if estimated_cost is None:
            estimated_cost = self.per_task_budget
        return self.remaining() >= estimated_cost * 0.1

    def next_task_budget(self) -> float:
        """Get budget for next task (min of per_task and remaining)."""
        return min(self.per_task_budget, self.remaining())

    def summary(self) -> str:
        """Return a summary string."""
        lines = [f"Total spent: ${self.total_spent:.4f} / ${self.max_budget:.2f}"]
        for tid, cost in self.task_costs.items():
            lines.append(f"  {tid}: ${cost:.4f}")
        return "\n".join(lines)


# ============================================================
# WIP File Operations
# ============================================================

def ensure_wip_dir():
    """Create .claude-flow/ directory if it doesn't exist."""
    os.makedirs(WIP_DIR, exist_ok=True)


def read_wip() -> Optional[str]:
    """Read WIP file content. Returns None if file doesn't exist."""
    try:
        with open(WIP_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def parse_wip_status(wip_content: Optional[str]) -> str:
    """Parse the status field from WIP file.

    Returns: 'done', 'need_human', 'active', or 'unknown'
    """
    if not wip_content:
        return "unknown"

    # Look for status in YAML frontmatter
    match = re.search(r"^status:\s*(\S+)", wip_content, re.MULTILINE)
    if match:
        status = match.group(1).strip().lower()
        if status == "done":
            return "done"
        if status in ("need_human", "blocked"):
            return "need_human"
        if status == "active":
            return "active"

    return "unknown"


def count_completed_tasks(wip_content: Optional[str]) -> int:
    """Count [x] items in WIP to track progress."""
    if not wip_content:
        return 0
    return len(re.findall(r"- \[x\]", wip_content, re.IGNORECASE))


def delete_wip():
    """Remove WIP file after goal is achieved."""
    try:
        os.remove(WIP_FILE)
    except FileNotFoundError:
        pass


# ============================================================
# Prompt Builders
# ============================================================

WIP_INSTRUCTIONS = f"""
## WIP Protocol (CRITICAL — you MUST follow this)

The file `{WIP_FILE}` is your persistent memory across sessions. You MUST:

1. **At the START of this session**: If `{WIP_FILE}` exists, read it first to understand prior progress.
2. **BEFORE budget runs out**: Write/update `{WIP_FILE}` with your progress using this exact format:

```markdown
---
status: active
goal: "<the goal>"
round: <N>
---

## Completed
- [x] <what was done, with specific details>

## Remaining
- [ ] <next task>
- [ ] <subsequent tasks>

## Strategies Tried
- <what worked and what didn't>

## Constraints
- <discovered limitations>

## Next Steps
<specific instructions for the next round — what to do first>
```

3. **If goal is achieved**: Update status to `done` and write a summary of what was accomplished.
4. **If you need human input**: Update status to `need_human` and explain what decision is needed.
5. **NEVER skip writing WIP** — it is the only way progress survives between sessions.
"""


def build_first_round_prompt(goal: str) -> str:
    """Build the prompt for round 1: fresh task."""
    return f"""{goal}

This is round 1 of a persistent loop that will keep running until the goal is achieved.
Push the goal as far as possible. If stuck, try self-rescue (change approach / decompose finer / deep search) before giving up.
{WIP_INSTRUCTIONS}"""


def build_resume_prompt(goal: str, round_num: int, wip_content: str) -> str:
    """Build the prompt for subsequent rounds: resume from WIP."""
    return f"""Continue working on this goal: {goal}

This is round {round_num} of an automatic persistent loop.

Here is the progress from previous rounds (from `{WIP_FILE}`):

---
{wip_content}
---

Resume from where the previous round left off. Do NOT repeat completed work.
Start from the "Next Steps" section above.
If stuck, try self-rescue (change approach / decompose finer / deep search) before giving up.
{WIP_INSTRUCTIONS}"""


# ============================================================
# Session Runner
# ============================================================

def _parse_claude_json(raw: str) -> dict:
    """Parse the JSON blob returned by ``claude --output-format json``.

    Expected top-level keys (all optional — we default gracefully):
        result          str   — the assistant's final text
        is_error        bool  — True when claude reports an error
        total_cost_usd  float — cumulative API cost for the session
        usage           dict  — {input_tokens, output_tokens, ...}
        duration_ms     int   — wall-clock ms for the session
        stop_reason     str   — e.g. "end_turn", "max_tokens", ...

    Returns a normalised dict with keys:
        output, cost_usd, input_tokens, output_tokens,
        duration_ms, stop_reason, success
    """
    _DEFAULTS = {
        "output":        "",
        "cost_usd":      0.0,
        "input_tokens":  0,
        "output_tokens": 0,
        "duration_ms":   0,
        "stop_reason":   "unknown",
        "success":       False,
    }

    if not raw or not raw.strip():
        return _DEFAULTS.copy()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat the raw text as the output so callers still see it.
        fallback = _DEFAULTS.copy()
        fallback["output"] = raw
        return fallback

    usage = data.get("usage") or {}
    is_error = bool(data.get("is_error", False))

    return {
        "output":        data.get("result") or "",
        "cost_usd":      float(data.get("total_cost_usd") or 0.0),
        "input_tokens":  int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "duration_ms":   int(data.get("duration_ms") or 0),
        "stop_reason":   str(data.get("stop_reason") or "unknown"),
        "success":       not is_error,
    }


def run_claude_session(
    prompt: str,
    timeout: int = 1800,
    budget_usd: Optional[float] = None,
) -> dict:
    """Launch a Claude Code session and return a structured result dict.

    Parameters
    ----------
    prompt:     The full prompt to pass to ``claude -p``.
    timeout:    Wall-clock seconds before the subprocess is killed.
    budget_usd: When provided, adds ``--max-budget-usd <value>`` to the
                command so Claude's own budget guard triggers first.

    Return keys
    -----------
    output        (str)   — assistant's final text
    cost_usd      (float) — total API cost in USD
    input_tokens  (int)
    output_tokens (int)
    duration_ms   (int)
    stop_reason   (str)
    success       (bool)  — False when claude reports is_error or on exception
    """
    # On Windows, shell=True + long prompts gets truncated by cmd.exe.
    # Feed prompt via stdin (claude -p without args reads from stdin).
    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]
    if budget_usd is not None:
        cmd += ["--max-budget-usd", str(budget_usd)]

    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            shell=(sys.platform == "win32"),
        )
        return _parse_claude_json(proc.stdout or "")

    except subprocess.TimeoutExpired:
        return {
            "output":        "[TIMEOUT] Session timed out",
            "cost_usd":      0.0,
            "input_tokens":  0,
            "output_tokens": 0,
            "duration_ms":   timeout * 1000,
            "stop_reason":   "timeout",
            "success":       False,
        }
    except FileNotFoundError:
        print("Error: 'claude' command not found. Make sure Claude Code is installed and in PATH.")
        sys.exit(1)


# ============================================================
# DAG Planning
# ============================================================

def build_clarify_prompt(goal: str) -> str:
    """Build a prompt asking Claude to evaluate whether the goal is clear enough to execute."""
    return f"""You are a task evaluator. Assess whether the following goal is clear enough to be decomposed into executable sub-tasks.

Goal: {goal}

Evaluate these dimensions:
1. **Scope**: Is it clear what is included and excluded?
2. **Acceptance criteria**: Can you determine when this is "done"?
3. **Technical approach**: Is there enough context to choose an implementation strategy?
4. **Ambiguities**: Are there terms, requirements, or constraints that could be interpreted multiple ways?

Output your assessment as JSON inside a ```json code fence:
```json
{{
  "clear": true/false,
  "confidence": 0.0-1.0,
  "questions": [
    "Question 1 that needs user clarification",
    "Question 2 ..."
  ],
  "assumptions": [
    "If no clarification: I would assume X",
    "If no clarification: I would assume Y"
  ]
}}
```

Rules:
- "clear" = true ONLY if confidence >= 0.8 AND no blocking questions exist.
- "questions" should contain ONLY questions where the answer materially changes the implementation approach. Do NOT ask trivial or obvious questions.
- "assumptions" should list what you would default to if the user doesn't answer. This lets the user decide whether the assumptions are acceptable.
- If the goal is already detailed with clear acceptance criteria, set clear=true and leave questions empty."""


def build_plan_prompt(goal: str) -> str:
    """Build a prompt asking Claude to analyze the goal and output a JSON DAG."""
    return f"""Analyze the following goal and break it down into a set of sub-tasks.

Goal: {goal}

Output a JSON array of task objects wrapped in a ```json code fence.
Each task object must have exactly these fields:
  - "id": a short unique string identifier (e.g. "task-1", "setup", "refactor-auth")
  - "description": a one-sentence description of what the task does
  - "acceptance_criteria": a concrete, verifiable statement of what "done" looks like
  - "dependencies": a list of task IDs that must be completed before this task starts (empty list if none)
  - "files": a list of file paths this task will create or modify (empty list if unknown)

Rules:
  - Order tasks so that independent tasks (no dependencies) come first.
  - Each task must be small enough to complete in a single focused session.
  - Do NOT include any explanation outside the ```json code fence.

Example output:
```json
[
  {{
    "id": "task-1",
    "description": "Set up project scaffolding",
    "acceptance_criteria": "Directory structure exists with all required config files",
    "dependencies": [],
    "files": ["pyproject.toml", "src/__init__.py"]
  }},
  {{
    "id": "task-2",
    "description": "Implement core logic",
    "acceptance_criteria": "All unit tests for core module pass",
    "dependencies": ["task-1"],
    "files": ["src/core.py", "tests/test_core.py"]
  }}
]
```"""


def parse_dag_response(response: str) -> RecursiveDAG:
    """Parse Claude's response to extract the JSON DAG.

    Looks for a ```json ... ``` code fence, parses the JSON array, and builds a
    RecursiveDAG from the result.  Falls back to a single-task DAG on any error.
    """
    try:
        match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
        if not match:
            raise ValueError("No ```json code fence found in response")

        raw_json = match.group(1)
        task_list = json.loads(raw_json)

        if not isinstance(task_list, list):
            raise ValueError("JSON root must be an array")

        tasks = []
        for item in task_list:
            task = RecursiveTask(
                id=str(item["id"]),
                description=str(item.get("description", "")),
                acceptance_criteria=str(item.get("acceptance_criteria", "")),
                dependencies=list(item.get("dependencies", [])),
                files=list(item.get("files", [])),
            )
            tasks.append(task)

        return RecursiveDAG(tasks)

    except Exception as exc:  # noqa: BLE001
        print(f"  [DAG] Failed to parse planning response ({exc}). Using single-task fallback.")
        fallback = RecursiveTask(
            id="task-1",
            description=response[:200] if response else "Complete the goal",
            acceptance_criteria="Goal is fully achieved",
            dependencies=[],
            files=[],
        )
        return RecursiveDAG([fallback])


def clarify_goal(goal: str, budget: BudgetTracker) -> str:
    """Evaluate whether the goal is clear enough; ask user for clarification if needed.

    Returns the (possibly refined) goal string. If the goal is already clear,
    returns it unchanged.
    """
    print("  [Clarify] Evaluating goal clarity...")
    prompt = build_clarify_prompt(goal)
    session = run_claude_session(prompt, budget_usd=budget.next_task_budget())
    budget.record("clarification", session["cost_usd"])

    output = session["output"]
    try:
        match = re.search(r"```json\s*([\s\S]*?)\s*```", output)
        if not match:
            raise ValueError("No JSON in clarification response")
        assessment = json.loads(match.group(1))
    except Exception:
        print("  [Clarify] Could not parse assessment, proceeding with original goal.")
        return goal

    confidence = assessment.get("confidence", 1.0)
    is_clear = assessment.get("clear", True)
    questions = assessment.get("questions", [])
    assumptions = assessment.get("assumptions", [])

    print(f"  [Clarify] Confidence: {confidence:.1f} | Clear: {is_clear}")

    if is_clear and not questions:
        print("  [Clarify] Goal is clear. Proceeding to planning.")
        return goal

    # --- Goal is ambiguous — ask user ---
    print(f"\n{'='*60}")
    print("GOAL CLARIFICATION NEEDED")
    print(f"{'='*60}")
    print(f"\nGoal: {goal}\n")

    if questions:
        print("Questions:")
        for i, q in enumerate(questions, 1):
            print(f"  {i}. {q}")

    if assumptions:
        print("\nDefault assumptions (if you skip):")
        for a in assumptions:
            print(f"  - {a}")

    print("\nOptions:")
    print("  - Answer the questions above to refine the goal")
    print("  - Press Enter to accept default assumptions and proceed")
    print("  - Type 'q' to abort")
    print()

    try:
        user_input = input("Your clarification (or Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  [Clarify] No TTY or interrupted. Proceeding with assumptions.")
        return goal

    if user_input.lower() == "q":
        print("  [Clarify] Aborted by user.")
        sys.exit(0)

    if user_input:
        # Append user's clarification to the goal
        goal = f"{goal}\n\nUser clarification:\n{user_input}"
        print("  [Clarify] Goal refined with user input.")
    else:
        if assumptions:
            assumptions_text = "\n".join(f"- {a}" for a in assumptions)
            goal = f"{goal}\n\nAssumptions (accepted by user):\n{assumptions_text}"
            print("  [Clarify] Proceeding with default assumptions.")

    return goal


def plan_dag(goal: str, budget: BudgetTracker) -> RecursiveDAG:
    """Orchestrate DAG planning: call Claude, record cost, parse, and return the DAG."""
    print("  [DAG] Planning sub-tasks...")
    prompt = build_plan_prompt(goal)
    session = run_claude_session(prompt, budget_usd=budget.next_task_budget())
    budget.record("planning", session["cost_usd"])

    dag = parse_dag_response(session["output"])

    print(f"  [DAG] Plan (cost ${session['cost_usd']:.4f}):")
    print(dag.summary())

    return dag


# ============================================================
# Task Execution
# ============================================================

def build_task_prompt(task: RecursiveTask, goal: str) -> str:
    """Build a prompt for executing a single sub-task."""
    files_section = ""
    if task.files:
        files_list = "\n".join(f"  - {f}" for f in task.files)
        files_section = f"\n## Files to Modify\n{files_list}\n"

    return f"""You are executing a single sub-task as part of a larger goal.

## Overall Goal
{goal}

## Your Sub-Task
Task ID: {task.id}
Description: {task.description}

## Acceptance Criteria
{task.acceptance_criteria}
{files_section}
## Instructions
1. Complete the task described above.
2. Before finishing, verify that ALL acceptance criteria listed above are satisfied.
3. Once the task is complete and verified, commit your changes with the message:
   `checkpoint: {task.id} {task.description}`
4. Do not proceed beyond the scope of this sub-task.
"""


def execute_task(task: RecursiveTask, goal: str, budget: BudgetTracker) -> dict:
    """Execute a single task atomically."""
    prompt = build_task_prompt(task, goal)
    result = run_claude_session(prompt, budget_usd=budget.next_task_budget())
    budget.record(task.id, result["cost_usd"])

    status_str = "success" if result["success"] else "fail"
    print(f"  Task {task.id}: [{status_str}] cost=${result['cost_usd']:.4f}")

    return result


def execute_parallel(tasks: list, goal: str, budget: BudgetTracker) -> list:
    """Execute multiple tasks in parallel using ThreadPoolExecutor."""
    _FAIL_RESULT = {
        "output": "", "cost_usd": 0.0, "input_tokens": 0,
        "output_tokens": 0, "duration_ms": 0, "stop_reason": "error",
        "success": False,
    }
    results = [None] * len(tasks)

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            executor.submit(execute_task, task, goal, budget): idx
            for idx, task in enumerate(tasks)
        }
        for future in futures:
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                print(f"  [ERROR] Task {tasks[idx].id} raised: {exc}")
                results[idx] = _FAIL_RESULT.copy()

    return results


def execute_dag(dag: RecursiveDAG, goal: str, budget: BudgetTracker) -> None:
    """Main DAG execution loop — runs tasks respecting dependencies and budget."""
    while dag.has_ready_tasks():
        if not budget.can_afford():
            print(f"\n[BUDGET EXHAUSTED] Remaining: ${budget.remaining():.4f}. Stopping DAG execution.")
            break

        ready = dag.get_ready_leaves()
        parallel, sequential = dag.get_parallel_groups(ready)

        # Execute parallel batch
        if parallel:
            print(f"\n  Executing {len(parallel)} task(s) in parallel: "
                  f"{[t.id for t in parallel]}")
            results = execute_parallel(parallel, goal, budget)
            for task, result in zip(parallel, results):
                if result["success"]:
                    dag.mark_done(task.id, result)
                else:
                    dag.mark_failed(task.id, result)

        # Execute sequential tasks one by one
        for task in sequential:
            if not budget.can_afford():
                print(f"\n[BUDGET EXHAUSTED] Remaining: ${budget.remaining():.4f}. Stopping DAG execution.")
                break
            print(f"\n  Executing task sequentially: {task.id}")
            result = execute_task(task, goal, budget)
            if result["success"]:
                dag.mark_done(task.id, result)
            else:
                dag.mark_failed(task.id, result)

        print(f"\n--- DAG Status ---\n{dag.summary()}\n"
              f"Budget: {budget.summary()}\n------------------")


# ============================================================
# Main Loop
# ============================================================

def persistent_solve(
    goal: str,
    max_rounds: int,
    max_time: int,
    max_budget_usd: float = 5.0,
    per_task_budget_usd: float = 0.5,
    mode: str = "dag",
    skip_clarify: bool = False,
):
    """Main persistent loop logic.

    Modes:
        dag   — Plan a DAG of sub-tasks, execute each as an independent
                ``claude -p`` call with budget tracking and parallel execution.
        legacy — Original behaviour: one full Claude session per round,
                 WIP-file handshake between rounds.
    """
    ensure_wip_dir()
    start_time = time.time()
    budget = BudgetTracker(max_budget_usd, per_task_budget_usd)

    print(f"{'='*60}")
    print("Persistent loop started")
    print(f"Goal: {goal}")
    print(f"Mode: {mode}")
    print(f"Max rounds: {max_rounds} | Max time: {max_time}s")
    print(f"Budget: ${max_budget_usd:.2f} total, ${per_task_budget_usd:.2f} per task")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if mode == "dag":
        _run_dag_mode(goal, max_rounds, max_time, budget, start_time, skip_clarify)
    else:
        _run_legacy_mode(goal, max_rounds, max_time, budget, start_time)

    # Final summary
    print(f"\n{'='*60}")
    print("Final budget summary:")
    print(f"  {budget.summary()}")
    print(f"  Total time: {int(time.time() - start_time)}s")
    print(f"{'='*60}")


def _run_dag_mode(
    goal: str,
    max_rounds: int,
    max_time: int,
    budget: BudgetTracker,
    start_time: float,
    skip_clarify: bool = False,
):
    """DAG mode: plan once, execute sub-tasks atomically with budget control."""
    original_goal = goal

    # Phase 0: Clarify goal before first round
    if not skip_clarify:
        goal = clarify_goal(goal, budget)
        original_goal = goal

    for round_num in range(1, max_rounds + 1):
        elapsed = time.time() - start_time
        if elapsed >= max_time:
            print(f"\n[CIRCUIT BREAKER] Total time exceeded {max_time}s.")
            break
        if not budget.can_afford():
            print(f"\n[CIRCUIT BREAKER] Budget exhausted (${budget.total_spent:.4f}/{budget.max_budget:.2f}).")
            break

        print(f"\n{'─'*60}")
        print(f"DAG Round {round_num}/{max_rounds} | "
              f"Elapsed {int(elapsed)}s | "
              f"Budget ${budget.remaining():.2f} remaining")
        print(f"{'─'*60}")

        # Phase 1: Plan
        dag = plan_dag(goal, budget)

        if not dag.tasks:
            print("  [DAG] No tasks generated. Stopping.")
            break

        # Phase 2: Execute
        execute_dag(dag, goal, budget)

        # Phase 3: Check results
        failed = [t for t in dag.tasks.values() if t.status == "failed"]
        done = [t for t in dag.tasks.values() if t.status == "done"]
        pending = [t for t in dag.tasks.values() if t.status == "pending"]

        print(f"\n  Round {round_num} result: {len(done)} done, {len(failed)} failed, {len(pending)} pending")

        if not failed and not pending:
            print(f"\n{'='*60}")
            print(f"All tasks completed in round {round_num}!")
            print(f"{'='*60}")
            return

        if failed and not pending:
            # All remaining tasks failed — rebuild DAG with failure context
            fail_ctx = "; ".join(
                f"{t.id} failed: {(t.result or {}).get('output', '')[:100]}"
                for t in failed
            )
            goal = f"{goal}\n\nPrevious attempt had failures:\n{fail_ctx}\nPlease adjust approach."
            print("  Rebuilding DAG with failure context for next round...")

        if pending:
            # Budget ran out mid-DAG — stop, user can re-run
            print(f"  {len(pending)} tasks still pending (likely budget exhausted).")
            break

    print(f"\nTo continue: python scripts/persistent-solve.py \"{original_goal}\"")


def _run_legacy_mode(
    goal: str,
    max_rounds: int,
    max_time: int,
    budget: BudgetTracker,
    start_time: float,
):
    """Legacy mode: one full Claude session per round with WIP handshake."""
    prev_completed = 0
    no_progress_count = 0

    existing_wip = read_wip()
    if existing_wip:
        prev_completed = count_completed_tasks(existing_wip)
        print(f"\nFound existing WIP ({prev_completed} tasks completed). Resuming.")

    for round_num in range(1, max_rounds + 1):
        elapsed = time.time() - start_time
        if elapsed >= max_time:
            print(f"\n[CIRCUIT BREAKER] Total time exceeded {max_time}s. Stopping.")
            break
        if no_progress_count >= MAX_CONSECUTIVE_NO_PROGRESS:
            print(f"\n[CIRCUIT BREAKER] {MAX_CONSECUTIVE_NO_PROGRESS} consecutive rounds with no progress. Stopping.")
            break
        if not budget.can_afford():
            print("\n[CIRCUIT BREAKER] Budget exhausted. Stopping.")
            break

        remaining_time = int(max_time - elapsed)
        session_timeout = min(1800, remaining_time)

        print(f"\n{'─'*60}")
        print(f"Round {round_num}/{max_rounds} | "
              f"Elapsed {int(elapsed)}s | "
              f"Remaining {remaining_time}s | "
              f"Budget ${budget.remaining():.2f}")
        print(f"{'─'*60}")

        wip_content = read_wip()
        if round_num == 1 and not wip_content:
            prompt = build_first_round_prompt(goal)
        else:
            wip_content = wip_content or f"No WIP file found. Starting fresh on goal: {goal}"
            prompt = build_resume_prompt(goal, round_num, wip_content)

        session = run_claude_session(prompt, timeout=session_timeout,
                                     budget_usd=budget.next_task_budget())
        output_text = session["output"]
        budget.record(f"round-{round_num}", session["cost_usd"])

        wip_after = read_wip()
        wip_status = parse_wip_status(wip_after)
        current_completed = count_completed_tasks(wip_after)

        if current_completed > prev_completed:
            no_progress_count = 0
            print(f"  Progress: {prev_completed} → {current_completed} tasks completed")
        elif wip_status == "done":
            no_progress_count = 0
        else:
            if wip_after and wip_after != wip_content:
                no_progress_count = 0
                print("  WIP updated (content changed)")
            else:
                no_progress_count += 1
                print(f"  [WARNING] No visible progress ({no_progress_count} consecutive)")

        prev_completed = current_completed

        if session["cost_usd"] > 0:
            print(f"  Session cost: ${session['cost_usd']:.4f} | "
                  f"tokens in/out: {session['input_tokens']}/{session['output_tokens']}")

        if wip_status == "done":
            print(f"\n{'='*60}")
            print(f"Goal achieved in round {round_num}!")
            print(f"{'='*60}")
            return

        if wip_status == "need_human":
            print(f"\n{'='*60}")
            print(f"Round {round_num} requires human decision.")
            print(f"Check {os.path.abspath(WIP_FILE)} for details.")
            print(f"{'='*60}")
            return

        if session["stop_reason"] == "timeout" or "[TIMEOUT]" in output_text:
            print("  Round timed out. WIP may not be saved.")

        if "[GOAL_ACHIEVED]" in output_text and wip_status != "done":
            print(f"\n{'='*60}")
            print(f"Goal achieved in round {round_num} (detected from output)!")
            print(f"{'='*60}")
            return

        print(f"  Round ended (WIP status: {wip_status}). Preparing next round...")
        time.sleep(3)

    print(f"\nPersistent loop ended. WIP saved at: {os.path.abspath(WIP_FILE)}")
    print(f"To continue: python scripts/persistent-solve.py \"{goal}\" --mode legacy")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Persistent Loop Scheduler — Atomic DAG execution with budget tracking"
    )
    parser.add_argument("goal", help="The goal to achieve")
    parser.add_argument(
        "--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS,
        help=f"Maximum rounds (default: {DEFAULT_MAX_ROUNDS})"
    )
    parser.add_argument(
        "--max-time", type=int, default=DEFAULT_MAX_TIME,
        help=f"Maximum total time in seconds (default: {DEFAULT_MAX_TIME})"
    )
    parser.add_argument(
        "--max-budget-usd", type=float, default=5.0,
        help="Maximum total budget in USD (default: 5.0)"
    )
    parser.add_argument(
        "--per-task-budget", type=float, default=0.5,
        help="Maximum budget per sub-task in USD (default: 0.5)"
    )
    parser.add_argument(
        "--mode", choices=["dag", "legacy"], default="dag",
        help="Execution mode: 'dag' (atomic sub-tasks) or 'legacy' (WIP handshake) (default: dag)"
    )
    parser.add_argument(
        "--no-clarify", action="store_true",
        help="Skip goal clarification phase and proceed directly to planning"
    )

    args = parser.parse_args()
    persistent_solve(
        args.goal,
        args.max_rounds,
        args.max_time,
        max_budget_usd=args.max_budget_usd,
        per_task_budget_usd=args.per_task_budget,
        mode=args.mode,
        skip_clarify=args.no_clarify,
    )


if __name__ == "__main__":
    main()
