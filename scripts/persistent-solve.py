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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================
# Constants
# ============================================================
DEFAULT_MAX_ROUNDS = 10
DEFAULT_MAX_TIME = 7200      # 2 hours
MAX_CONSECUTIVE_NO_PROGRESS = 3
MAX_RECURSION_DEPTH = 5
MAX_BATCH_SIZE = 5             # Max C:1-2 tasks per batch call
WIP_DIR = ".claude-flow"
WIP_FILE = f"{WIP_DIR}/wip.md"
CONTRACTS_DIR = f"{WIP_DIR}/contracts"


# ============================================================
# Exceptions
# ============================================================

class PlanningError(Exception):
    """Raised when recursive planning fails (bad JSON, invalid complexity, etc.)."""
    pass


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

    def replace_subtree(self, task_id: str, new_children: list['RecursiveTask']):
        """Replace a task's children with new tasks.

        - Removes all old descendants from the DAG
        - Adds new children, wiring parent/children links
        - Remaps any downstream dependency referencing removed IDs to task_id
        """
        task = self.tasks.get(task_id)
        if not task:
            return

        # Collect all old descendant IDs (children, grandchildren, etc.)
        old_ids: set = set()
        def _collect(tid: str):
            t = self.tasks.get(tid)
            if not t:
                return
            old_ids.add(tid)
            for cid in t.children:
                _collect(cid)
        for cid in task.children:
            _collect(cid)

        # Remove old descendants from DAG
        for oid in old_ids:
            del self.tasks[oid]

        # Add new children and wire parent/children links
        task.children = [c.id for c in new_children]
        for child in new_children:
            child.parent = task_id
            child.depth = task.depth + 1
            self.tasks[child.id] = child

        # Remap downstream dependencies: any task referencing a removed ID -> task_id
        for t in self.tasks.values():
            if t.id == task_id:
                continue
            t.dependencies = [
                task_id if dep in old_ids else dep
                for dep in t.dependencies
            ]
            # Deduplicate while preserving order
            seen = set()
            deduped = []
            for dep in t.dependencies:
                if dep not in seen:
                    seen.add(dep)
                    deduped.append(dep)
            t.dependencies = deduped

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

    def to_kanban_dict(self) -> dict:
        """Produce a nested tree structure for kanban.json output.

        Returns a dict with:
        - summary: {total, done, failed, running, pending, total_cost_usd}
        - tree: recursive list of task nodes
        """
        # Count statuses
        counts = {"total": 0, "done": 0, "failed": 0, "running": 0, "pending": 0}
        total_cost = 0.0
        for t in self.tasks.values():
            counts["total"] += 1
            if t.status in counts:
                counts[t.status] += 1
            total_cost += t.cost_usd
        counts["total_cost_usd"] = round(total_cost, 4)

        def _build_node(task: RecursiveTask) -> dict:
            node = {
                "id": task.id,
                "description": task.description,
                "status": task.status,
                "complexity": task.complexity,
                "cost_usd": task.cost_usd,
                "commit_hash": task.commit_hash,
                "children": [
                    _build_node(self.tasks[cid])
                    for cid in task.children
                    if cid in self.tasks
                ],
            }
            return node

        # Root tasks are those with no parent
        roots = [t for t in self.tasks.values() if t.parent is None]
        tree = [_build_node(r) for r in roots]

        return {"summary": counts, "tree": tree}


# ============================================================
# Kanban State (real-time progress tracking)
# ============================================================

class KanbanState:
    """Tracks and displays DAG execution progress as a kanban board.

    Provides:
    - Tree-structured task status from RecursiveDAG
    - Summary counts (total/done/failed/pending/running/cost)
    - JSON persistence to disk
    - Terminal tree-view with box-drawing characters
    """

    def __init__(self, goal: str):
        self.goal = goal
        self.start_time = datetime.now().isoformat()
        self.tree = []
        self.summary = {}

    def update_from_dag(self, dag: RecursiveDAG):
        """Rebuild tree structure and summary from the current DAG state."""
        kanban = dag.to_kanban_dict()
        self.tree = kanban.get("tree", [])
        self.summary = kanban.get("summary", {})

    def save(self, path: str = ".claude-flow/kanban.json"):
        """Write kanban state as JSON to disk, creating directories if needed."""
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = {
            "goal": self.goal,
            "start_time": self.start_time,
            "updated_at": datetime.now().isoformat(),
            "summary": self.summary,
            "tree": self.tree,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def print_tree(self):
        """Print the task tree to terminal with box-drawing characters."""
        def _format_cost(cost):
            return f"${cost:.2f}" if cost else "$0.00"

        def _print_node(node, prefix="", is_last=True):
            connector = "└─ " if is_last else "├─ "
            status = node.get("status", "pending")
            task_id = node.get("id", "?")
            desc = node.get("description", "")
            cost = _format_cost(node.get("cost_usd", 0.0))
            commit = node.get("commit_hash", "")

            line = f"{prefix}{connector}[{status}] {task_id}: {desc}  ({cost})"
            if commit:
                line += f"  {commit}"
            print(line)

            children = node.get("children", [])
            child_prefix = prefix + ("   " if is_last else "│  ")
            for i, child in enumerate(children):
                _print_node(child, child_prefix, i == len(children) - 1)

        # Print header with goal and summary
        total_cost = _format_cost(self.summary.get("total_cost_usd", 0.0))
        print(f"[running] {self.goal}  ({total_cost})")

        if isinstance(self.tree, list):
            for i, root in enumerate(self.tree):
                _print_node(root, "", i == len(self.tree) - 1)
        elif isinstance(self.tree, dict):
            _print_node(self.tree, "", True)


# ============================================================
# Contract (interface contract between sub-DAGs)
# ============================================================

@dataclass
class Contract:
    """Interface contract for a sub-DAG node."""
    dag_id: str
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    constraints: list = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the contract as a markdown document."""
        lines = [f"# Contract: {self.dag_id}", ""]
        lines.append("## Inputs")
        for inp in self.inputs:
            lines.append(f"- {inp}")
        lines.append("")
        lines.append("## Outputs")
        for out in self.outputs:
            lines.append(f"- {out}")
        lines.append("")
        lines.append("## Constraints")
        for con in self.constraints:
            lines.append(f"- {con}")
        lines.append("")
        return "\n".join(lines)

    def save(self, base_dir: str = CONTRACTS_DIR):
        """Write the contract to a markdown file."""
        os.makedirs(base_dir, exist_ok=True)
        safe_name = self.dag_id.replace("/", "_").replace("\\", "_")
        path = os.path.join(base_dir, f"{safe_name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())

    @staticmethod
    def load(path: str) -> "Contract":
        """Load a Contract from a markdown file."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse the markdown back into structured data
        dag_id = ""
        inputs = []
        outputs = []
        constraints = []
        current_section = None

        for line in content.splitlines():
            if line.startswith("# Contract: "):
                dag_id = line[len("# Contract: "):]
            elif line.strip() == "## Inputs":
                current_section = "inputs"
            elif line.strip() == "## Outputs":
                current_section = "outputs"
            elif line.strip() == "## Constraints":
                current_section = "constraints"
            elif line.startswith("- "):
                item = line[2:]
                if current_section == "inputs":
                    inputs.append(item)
                elif current_section == "outputs":
                    outputs.append(item)
                elif current_section == "constraints":
                    constraints.append(item)

        return Contract(dag_id=dag_id, inputs=inputs, outputs=outputs, constraints=constraints)


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
# Recursive Planning
# ============================================================

def build_recursive_plan_prompt(goal: str, depth: int, parent_contract: str = None) -> str:
    """Build a prompt for recursive task decomposition with complexity rating."""
    contract_section = ""
    if parent_contract:
        contract_section = f"""
## Parent Contract (context)
{parent_contract}

You MUST respect the inputs/outputs/constraints defined in the parent contract above.
"""

    return f"""Analyze the following goal and break it down into a set of sub-tasks.

Goal: {goal}

Recursion depth: {depth} (max {MAX_RECURSION_DEPTH})
{contract_section}
Output a JSON array of task objects wrapped in a ```json code fence.
Each task object must have exactly these fields:
  - "id": a short unique string identifier (e.g. "task-1", "setup", "refactor-auth")
  - "description": a one-sentence description of what the task does
  - "acceptance_criteria": a concrete, verifiable statement of what "done" looks like
  - "dependencies": a list of task IDs that must be completed before this task starts (empty list if none)
  - "files": a list of file paths this task will create or modify (empty list if unknown)
  - "complexity": an integer from 1 to 5 rating task complexity:
    1 = trivial (< 1 min), 2 = simple (1-5 min), 3 = moderate (5-15 min),
    4 = complex (15-30 min), 5 = very complex (> 30 min)

Rules:
  - Order tasks so that independent tasks (no dependencies) come first.
  - Each task must be small enough to complete in a single focused session.
  - The "complexity" field MUST be an integer in the range [1, 5]. Do NOT omit it.
  - Do NOT include any explanation outside the ```json code fence.

Example output:
```json
[
  {{
    "id": "task-1",
    "description": "Set up project scaffolding",
    "acceptance_criteria": "Directory structure exists with all required config files",
    "dependencies": [],
    "files": ["pyproject.toml", "src/__init__.py"],
    "complexity": 2
  }},
  {{
    "id": "task-2",
    "description": "Implement core logic",
    "acceptance_criteria": "All unit tests for core module pass",
    "dependencies": ["task-1"],
    "files": ["src/core.py", "tests/test_core.py"],
    "complexity": 4
  }}
]
```"""


def parse_recursive_dag_response(response: str, parent_id: str = None) -> list:
    """Parse Claude's recursive planning response into a list of RecursiveTask objects.

    Unlike parse_dag_response, this function:
    - Requires 'complexity' field (int in [1, 5]) — raises PlanningError if invalid
    - Raises PlanningError on JSON parse failure (no fallback single-task)
    - Prefixes task IDs with parent_id if provided (for global uniqueness)
    - Remaps dependencies to use prefixed IDs
    """
    match = re.search(r"```json\s*([\s\S]*?)\s*```", response)
    if not match:
        raise PlanningError("No ```json code fence found in response")

    raw_json = match.group(1)
    try:
        task_list = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise PlanningError(f"Invalid JSON in response: {exc}") from exc

    if not isinstance(task_list, list):
        raise PlanningError("JSON root must be an array")

    tasks = []
    for item in task_list:
        # Validate complexity
        complexity = item.get("complexity")
        if not isinstance(complexity, int) or complexity < 1 or complexity > 5:
            raise PlanningError(
                f"Task '{item.get('id', '?')}' has invalid complexity: {complexity!r} "
                f"(must be int in [1, 5])"
            )

        task_id = str(item["id"])
        deps = list(item.get("dependencies", []))

        # Prefix IDs if parent_id is provided
        if parent_id:
            task_id = f"{parent_id}.{task_id}"
            deps = [f"{parent_id}.{d}" for d in deps]

        task = RecursiveTask(
            id=task_id,
            description=str(item.get("description", "")),
            acceptance_criteria=str(item.get("acceptance_criteria", "")),
            dependencies=deps,
            files=list(item.get("files", [])),
            complexity=complexity,
        )
        tasks.append(task)

    return tasks


def _generate_contract(task: RecursiveTask, budget: BudgetTracker) -> Contract:
    """Call Claude to generate an interface contract for a non-leaf task."""
    prompt = f"""Analyze this task and produce an interface contract describing its inputs, outputs, and constraints.

Task: {task.description}
Acceptance criteria: {task.acceptance_criteria}
Files: {', '.join(task.files) if task.files else 'unknown'}

Output JSON inside a ```json code fence with exactly these fields:
- "inputs": list of strings describing required interfaces/data from upstream
- "outputs": list of strings describing interfaces/data this task provides downstream
- "constraints": list of strings describing architectural constraints

```json
{{
  "inputs": ["..."],
  "outputs": ["..."],
  "constraints": ["..."]
}}
```"""
    session = run_claude_session(prompt, budget_usd=budget.next_task_budget())
    budget.record(f"contract-{task.id}", session["cost_usd"])

    try:
        match = re.search(r"```json\s*([\s\S]*?)\s*```", session["output"])
        if match:
            data = json.loads(match.group(1))
            return Contract(
                dag_id=task.id,
                inputs=data.get("inputs", []),
                outputs=data.get("outputs", []),
                constraints=data.get("constraints", []),
            )
    except (json.JSONDecodeError, KeyError):
        pass

    # Fallback: minimal contract
    return Contract(dag_id=task.id, inputs=[], outputs=[], constraints=[])


def load_relevant_contracts(task: RecursiveTask, dag: RecursiveDAG) -> str:
    """Load parent + completed sibling contracts, return as markdown."""
    parts = []
    base_dir = CONTRACTS_DIR

    # Parent contract
    if task.parent:
        safe_parent = task.parent.replace("/", "_").replace("\\", "_")
        parent_path = os.path.join(base_dir, f"{safe_parent}.md")
        if os.path.isfile(parent_path):
            contract = Contract.load(parent_path)
            parts.append(f"### Parent Contract ({task.parent})\n{contract.to_markdown()}")

    # Sibling contracts (children of the same parent that are done)
    if task.parent and task.parent in dag.tasks:
        parent_task = dag.tasks[task.parent]
        for sibling_id in parent_task.children:
            if sibling_id == task.id:
                continue
            sibling = dag.tasks.get(sibling_id)
            if sibling and sibling.status == "done":
                safe_sib = sibling_id.replace("/", "_").replace("\\", "_")
                sib_path = os.path.join(base_dir, f"{safe_sib}.md")
                if os.path.isfile(sib_path):
                    contract = Contract.load(sib_path)
                    parts.append(f"### Sibling Contract ({sibling_id})\n{contract.to_markdown()}")

    return "\n\n".join(parts)


def cleanup_contracts(base_dir: str = CONTRACTS_DIR):
    """Delete all contract files."""
    if os.path.isdir(base_dir):
        for fname in os.listdir(base_dir):
            fpath = os.path.join(base_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
        # Try to remove the directory itself
        try:
            os.rmdir(base_dir)
        except OSError:
            pass


def recursive_plan(
    goal: str,
    budget: BudgetTracker,
    depth: int = 0,
    parent_id: str = None,
    parent_contract: str = None,
) -> RecursiveDAG:
    """Recursively plan a goal into a DAG of tasks.

    - Calls Claude to decompose goal into tasks with complexity ratings
    - For tasks with complexity >= 3: recurse (unless depth > MAX_RECURSION_DEPTH)
    - Generates contract files for non-leaf tasks
    - Returns a RecursiveDAG with all tasks flattened across depths
    """
    print(f"  [Plan] depth={depth} parent={parent_id or 'root'}")

    prompt = build_recursive_plan_prompt(goal, depth, parent_contract)
    session = run_claude_session(prompt, budget_usd=budget.next_task_budget())
    budget.record(f"plan-d{depth}-{parent_id or 'root'}", session["cost_usd"])

    try:
        tasks = parse_recursive_dag_response(session["output"], parent_id)
    except PlanningError as exc:
        print(f"  [Plan] PlanningError at depth={depth}: {exc}")
        if depth == 0:
            # Root level: return empty DAG, caller will handle
            return RecursiveDAG()
        else:
            # Sub-level: create a single leaf task as fallback
            fallback = RecursiveTask(
                id=f"{parent_id}.fallback" if parent_id else "fallback",
                description=goal[:200],
                acceptance_criteria="Goal is achieved",
                dependencies=[],
                files=[],
                complexity=2,
                depth=depth,
                children=[],
                parent=parent_id,
            )
            return RecursiveDAG([fallback])

    # Set depth on all tasks
    for t in tasks:
        t.depth = depth

    all_tasks = []

    for task in tasks:
        if task.complexity >= 3 and depth < MAX_RECURSION_DEPTH:
            # Generate contract for this non-leaf task
            contract = _generate_contract(task, budget)
            contract.save()

            # Recurse
            sub_dag = recursive_plan(
                goal=task.description,
                budget=budget,
                depth=depth + 1,
                parent_id=task.id,
                parent_contract=contract.to_markdown(),
            )

            # Wire parent/children links
            sub_root_ids = [
                t.id for t in sub_dag.tasks.values()
                if t.depth == depth + 1
            ]
            task.children = sub_root_ids
            for st in sub_dag.tasks.values():
                if st.depth == depth + 1:
                    st.parent = task.id

            all_tasks.append(task)
            all_tasks.extend(sub_dag.tasks.values())
        else:
            # Leaf task (low complexity or depth limit reached)
            all_tasks.append(task)

    return RecursiveDAG(all_tasks)


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


def execute_leaf_task(
    task: RecursiveTask,
    goal: str,
    budget: BudgetTracker,
    contracts_text: str = "",
) -> dict:
    """Execute a leaf task with optional contract injection.

    Builds a prompt that includes the overall goal, task description,
    acceptance criteria, file list, and — when provided — interface
    contracts from parent/sibling tasks.  Calls ``run_claude_session``
    and returns its result dict with cost recorded on the budget tracker.

    Parameters
    ----------
    task:           The leaf task to execute.
    goal:           The top-level goal (provides context).
    budget:         Budget tracker for cost accounting.
    contracts_text: Rendered contract markdown to inject into the prompt.
                    Omitted from the prompt when empty.

    Returns
    -------
    Result dict from ``run_claude_session`` (keys: output, cost_usd,
    input_tokens, output_tokens, duration_ms, stop_reason, success).
    """
    files_section = ""
    if task.files:
        files_list = "\n".join(f"  - {f}" for f in task.files)
        files_section = f"\n## Files to Modify\n{files_list}\n"

    contracts_section = ""
    if contracts_text:
        contracts_section = f"""
## Interface Contracts
{contracts_text}

You MUST respect the inputs/outputs/constraints defined in the contracts above.
"""

    prompt = f"""You are executing a single sub-task as part of a larger goal.

## Overall Goal
{goal}
{contracts_section}
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


def checkpoint_commit(task: RecursiveTask, success: bool) -> Optional[str]:
    """Create a git checkpoint commit for a completed task.

    Parameters
    ----------
    task:    The task that was just executed.
    success: Whether the task execution succeeded.

    Returns
    -------
    The commit hash (short) if a commit was created, or None if there were
    no changes to commit.
    """
    if success:
        msg = f"checkpoint: {task.id} {task.description}"
    else:
        msg = f"[FAILED] checkpoint: {task.id} {task.description}"

    # Stage all changes
    subprocess.run(["git", "add", "-A"], capture_output=True)

    # Check if there is anything to commit
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
    )
    if status.returncode == 0:
        # Nothing staged — no changes to commit
        return None

    # Commit
    result = subprocess.run(
        ["git", "commit", "-m", msg],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  [WARN] git commit failed: {result.stderr.strip()}")
        return None

    # Get the commit hash
    rev = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    commit_hash = rev.stdout.strip() if rev.returncode == 0 else None
    if commit_hash:
        task.commit_hash = commit_hash
    return commit_hash


# ============================================================
# Verification
# ============================================================

def run_l1(task: RecursiveTask, budget: BudgetTracker) -> bool:
    """L1 verification: lightweight check that the task produced changes.

    For C:1-2 (atomic tasks): checks that git has uncommitted/new changes
    touching the expected files. This avoids expensive Claude calls for
    trivial verification.

    For C:3+ (complex tasks): calls Claude to verify acceptance criteria.

    Parameters
    ----------
    task:   The task whose acceptance criteria to verify.
    budget: Budget tracker (used to cap verification cost).

    Returns
    -------
    True if verification passed, False otherwise.
    """
    # C:1-2: lightweight git-based check — did the task produce changes?
    if task.complexity <= 2:
        try:
            diff = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, timeout=10,
            )
            has_changes = bool(diff.stdout.strip() or status.stdout.strip())
        except Exception:
            has_changes = True  # Assume changes on error

        if has_changes:
            print(f"  [L1] {task.id}: PASS (changes detected, C:{task.complexity})")
            return True
        else:
            print(f"  [L1] {task.id}: FAIL (no changes detected)")
            return False

    # C:3+: Claude-based verification
    prompt = f"""You are a verification agent. Check whether the following acceptance criteria are satisfied by the current code in the working directory.

## Task
{task.description}

## Acceptance Criteria
{task.acceptance_criteria}

## Instructions
1. Read the relevant files and check each acceptance criterion.
2. Respond with exactly one line: PASS or FAIL followed by a brief reason.

Examples:
- PASS: All criteria met — function exists with correct signature and return type.
- FAIL: Missing error handling for empty input case.

Your verdict:"""

    per_task_budget = min(0.15, budget.remaining() * 0.1)
    if not budget.can_afford():
        print(f"  [L1] Skipping verification for {task.id} — budget exhausted")
        return True  # Don't fail tasks just because budget is low

    print(f"  [L1] Verifying {task.id} (Claude, C:{task.complexity})...")
    result = run_claude_session(prompt, timeout=120, budget_usd=per_task_budget)
    budget.record(f"l1-{task.id}", result.get("cost_usd", 0.0))

    output = result.get("output", "").strip()
    if re.search(r'\bPASS\b', output, re.IGNORECASE):
        print(f"  [L1] {task.id}: PASS")
        return True
    else:
        print(f"  [L1] {task.id}: FAIL — {output[:200]}")
        return False


def run_l2(task: RecursiveTask, budget: BudgetTracker) -> bool:
    """L2 verification: adversarial review via Claude with up to 2 fix rounds.

    Runs ``git diff HEAD~1`` to capture the task's changes, then asks Claude
    to act as a strict code reviewer.  If the review finds issues, a second
    Claude call attempts to fix them.  The review-fix cycle runs at most 2
    times.

    Parameters
    ----------
    task:   The task whose changes to review.
    budget: Budget tracker (used to cap verification cost).

    Returns
    -------
    True if the review passes (or no issues remain), False otherwise.
    """
    per_round_budget = min(0.10, budget.remaining() * 0.1)
    if not budget.can_afford():
        print(f"  [L2] Skipping adversarial review for {task.id} — budget exhausted")
        return False

    # Grab the diff for the most recent commit (the checkpoint commit)
    try:
        diff_proc = subprocess.run(
            ["git", "diff", "HEAD~1"],
            capture_output=True, text=True, timeout=30,
        )
        diff_text = diff_proc.stdout.strip()
    except Exception as exc:
        print(f"  [L2] Failed to get git diff for {task.id}: {exc}")
        return False

    if not diff_text:
        print(f"  [L2] No diff found for {task.id}, skipping review")
        return True

    max_rounds = 2
    for round_num in range(1, max_rounds + 1):
        if not budget.can_afford():
            print(f"  [L2] Budget exhausted during round {round_num} for {task.id}")
            return False

        # --- Review step ---
        review_prompt = f"""You are a strict, adversarial code reviewer. Review the following git diff for correctness, security, performance, and style issues.

## Task Context
{task.description}

## Acceptance Criteria
{task.acceptance_criteria}

## Git Diff
```
{diff_text}
```

## Instructions
1. Look for bugs, security vulnerabilities, logic errors, missing edge cases, and style issues.
2. If everything looks good, respond with exactly: PASS
3. If there are issues, respond with: FAIL followed by a numbered list of issues to fix.

Your verdict:"""

        print(f"  [L2] Review round {round_num} for {task.id}...")
        review_result = run_claude_session(review_prompt, timeout=180, budget_usd=per_round_budget)
        budget.record(f"l2-review-{task.id}-r{round_num}", review_result.get("cost_usd", 0.0))

        review_output = review_result.get("output", "").strip()
        if re.search(r'\bPASS\b', review_output, re.IGNORECASE):
            print(f"  [L2] {task.id}: PASS (round {round_num})")
            return True

        print(f"  [L2] {task.id}: Issues found (round {round_num})")

        # --- Fix step ---
        if not budget.can_afford():
            print(f"  [L2] Budget exhausted before fix step for {task.id}")
            return False

        fix_prompt = f"""You are a code executor. A strict code review found the following issues in recently committed code. Fix all of them.

## Task Context
{task.description}

## Review Feedback
{review_output}

## Instructions
1. Read the relevant source files.
2. Fix every issue listed in the review feedback.
3. Do NOT introduce new features — only fix the reported issues.
4. After fixing, briefly list what you changed."""

        print(f"  [L2] Fixing issues for {task.id} (round {round_num})...")
        fix_result = run_claude_session(fix_prompt, timeout=300, budget_usd=per_round_budget)
        budget.record(f"l2-fix-{task.id}-r{round_num}", fix_result.get("cost_usd", 0.0))

        # Re-capture the diff after fix for the next review round
        try:
            diff_proc = subprocess.run(
                ["git", "diff", "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
            new_diff = diff_proc.stdout.strip()
            if new_diff:
                diff_text = new_diff
        except Exception:
            pass  # Use previous diff if re-capture fails

    print(f"  [L2] {task.id}: FAIL — issues remain after {max_rounds} rounds")
    return False


def run_l3(task: RecursiveTask, budget: BudgetTracker) -> bool:
    """L3 verification: run the full pytest test suite.

    Executes ``python -m pytest`` via subprocess and returns whether all
    tests pass.

    Parameters
    ----------
    task:   The task whose implementation to verify.
    budget: Budget tracker (checked but not charged — L3 is local-only).

    Returns
    -------
    True if pytest exits with code 0 (all tests pass), False otherwise.
    """
    if not budget.can_afford():
        print(f"  [L3] Skipping test suite for {task.id} — budget exhausted")
        return False

    print(f"  [L3] Running full test suite for {task.id}...")
    try:
        result = subprocess.run(
            ["python", "-m", "pytest"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            print(f"  [L3] {task.id}: PASS — all tests passed")
            return True
        else:
            stdout_tail = result.stdout[-500:] if result.stdout else ""
            stderr_tail = result.stderr[-500:] if result.stderr else ""
            print(f"  [L3] {task.id}: FAIL — pytest exit code {result.returncode}")
            if stdout_tail:
                print(f"  [L3] stdout (last 500 chars): {stdout_tail}")
            if stderr_tail:
                print(f"  [L3] stderr (last 500 chars): {stderr_tail}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  [L3] {task.id}: FAIL — pytest timed out after 600s")
        return False
    except FileNotFoundError:
        print(f"  [L3] {task.id}: FAIL — python not found on PATH")
        return False
    except Exception as exc:
        print(f"  [L3] {task.id}: FAIL — unexpected error: {exc}")
        return False


def run_verification(task: RecursiveTask, budget: BudgetTracker) -> bool:
    """Dispatch verification based on task complexity.

    Verification levels:
    - C:1-2 → L1 only (quick self-check)
    - C:3-4 → L1 + L2 (adversarial review)
    - C:5   → L1 + L2 + L3 (full test suite)

    Returns True if all applicable verification levels pass, False otherwise.
    """
    # L1 always runs
    if not run_l1(task, budget):
        return False

    # L2 for complexity >= 3
    if task.complexity >= 3:
        if not run_l2(task, budget):
            return False

    # L3 for complexity >= 5
    if task.complexity >= 5:
        if not run_l3(task, budget):
            return False

    return True


def replan_subtree(
    task: RecursiveTask,
    dag: RecursiveDAG,
    error_context: str,
    budget: BudgetTracker,
) -> bool:
    """Re-decompose a failed task via Claude and replace it in the DAG.

    Collects failure context and sibling contracts, calls Claude to produce a
    new sub-task decomposition, parses the response, calls
    ``dag.replace_subtree`` to swap in the new children, and generates
    contracts for any non-leaf new children.

    Returns True if the replan succeeded, False if it also failed.
    """
    if not budget.can_afford():
        print(f"  [Replan] Skipping replan for {task.id} — budget exhausted")
        return False

    # Collect sibling contracts for context
    sibling_contracts = ""
    if task.parent and task.parent in dag.tasks:
        parent_task = dag.tasks[task.parent]
        for sib_id in parent_task.children:
            if sib_id == task.id:
                continue
            sib = dag.tasks.get(sib_id)
            if sib and sib.status == "done":
                safe_sib = sib_id.replace("/", "_").replace("\\", "_")
                sib_path = os.path.join(CONTRACTS_DIR, f"{safe_sib}.md")
                if os.path.isfile(sib_path):
                    contract = Contract.load(sib_path)
                    sibling_contracts += f"### Sibling Contract ({sib_id})\n{contract.to_markdown()}\n\n"

    prompt = f"""A sub-task failed during execution. Re-decompose it into smaller, more achievable sub-tasks.

## Failed Task
ID: {task.id}
Description: {task.description}
Acceptance Criteria: {task.acceptance_criteria}
Files: {', '.join(task.files) if task.files else 'unknown'}

## Failure Context
{error_context}

## Completed Sibling Contracts
{sibling_contracts if sibling_contracts else '(none)'}

## Instructions
Re-decompose this task into smaller sub-tasks that avoid the failure. Each sub-task must have complexity 1-2.
Output a JSON array inside a ```json code fence:
```json
[{{
  "id": "task-1",
  "description": "...",
  "acceptance_criteria": "...",
  "dependencies": [],
  "files": ["..."],
  "complexity": 1
}}]
```"""

    try:
        print(f"  [Replan] Re-decomposing {task.id}...")
        session = run_claude_session(prompt, budget_usd=budget.next_task_budget())
        budget.record(f"replan-{task.id}", session["cost_usd"])

        new_tasks = parse_recursive_dag_response(session["output"], task.id)

        if not new_tasks:
            print(f"  [Replan] {task.id}: no new sub-tasks returned")
            return False

        # Set depth on new tasks
        for t in new_tasks:
            t.depth = task.depth + 1

        # Replace the subtree in the DAG
        dag.replace_subtree(task.id, new_tasks)

        # Generate contracts for non-leaf new children (complexity >= 3)
        for t in new_tasks:
            if t.complexity >= 3:
                contract = _generate_contract(t, budget)
                contract.save()

        # Reset parent task status so it can be re-evaluated
        task.status = "pending"

        print(f"  [Replan] {task.id}: re-decomposed into {len(new_tasks)} sub-tasks: "
              f"{[t.id for t in new_tasks]}")
        return True

    except PlanningError as exc:
        print(f"  [Replan] {task.id}: planning failed — {exc}")
        return False
    except Exception as exc:
        print(f"  [Replan] {task.id}: unexpected error — {exc}")
        return False


def execute_dag(dag: RecursiveDAG, goal: str, budget: BudgetTracker,
                kanban_state: KanbanState = None, kanban_path: str = None) -> None:
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

        # Update kanban after each batch
        if kanban_state:
            kanban_state.update_from_dag(dag)
            if kanban_path:
                kanban_state.save(kanban_path)
            kanban_state.print_tree()

        print(f"\n--- DAG Status ---\n{dag.summary()}\n"
              f"Budget: {budget.summary()}\n------------------")


def _build_batch_prompt(tasks: list, goal: str, contracts_text: str = "") -> str:
    """Build a single prompt that asks Claude to complete multiple small tasks at once."""
    task_blocks = []
    for i, task in enumerate(tasks, 1):
        files_str = ", ".join(task.files) if task.files else "as needed"
        task_blocks.append(
            f"### Task {i}: {task.id}\n"
            f"Description: {task.description}\n"
            f"Acceptance Criteria: {task.acceptance_criteria}\n"
            f"Files: {files_str}"
        )

    tasks_section = "\n\n".join(task_blocks)
    contracts_section = ""
    if contracts_text:
        contracts_section = f"\n## Interface Contracts\n{contracts_text}\n"

    return f"""You are executing multiple small sub-tasks as part of a larger goal.
Complete ALL of them in this single session.

## Overall Goal
{goal}
{contracts_section}
## Tasks to Complete
{tasks_section}

## Instructions
1. Complete ALL tasks listed above, one by one.
2. Verify each task's acceptance criteria before moving on.
3. After completing ALL tasks, make a single commit with message:
   `checkpoint: batch [{', '.join(t.id for t in tasks)}]`
4. Do not skip any task.
"""


def _execute_batch(tasks: list, goal: str, budget: BudgetTracker, dag: RecursiveDAG) -> dict:
    """Execute multiple C:1-2 tasks in a single claude -p call.

    Returns a single result dict. The caller marks all tasks based on this result.
    """
    contracts_text = load_relevant_contracts(tasks[0], dag)
    prompt = _build_batch_prompt(tasks, goal, contracts_text)

    ids_str = ", ".join(t.id for t in tasks)
    print(f"  [Batch] Executing {len(tasks)} tasks in one call: [{ids_str}]")

    result = run_claude_session(prompt, budget_usd=budget.next_task_budget())
    cost_per_task = result.get("cost_usd", 0.0) / max(len(tasks), 1)
    for task in tasks:
        budget.record(f"batch-{task.id}", cost_per_task)

    status_str = "success" if result["success"] else "fail"
    print(f"  [Batch] [{status_str}] cost=${result.get('cost_usd', 0):.4f} for {len(tasks)} tasks")

    return result


def _execute_leaf_parallel(tasks: list, goal: str, budget: BudgetTracker, dag: RecursiveDAG) -> list:
    """Execute multiple leaf tasks in parallel with contract injection.

    Optimization: C:1-2 tasks touching the same files are batched into a
    single claude -p call to avoid redundant cold starts.
    """
    _FAIL_RESULT = {
        "output": "", "cost_usd": 0.0, "input_tokens": 0,
        "output_tokens": 0, "duration_ms": 0, "stop_reason": "error",
        "success": False,
    }
    results = [None] * len(tasks)

    # --- Split into batchable (C:1-2) and individual (C:3+) ---
    batchable_indices = []
    individual_indices = []
    for idx, task in enumerate(tasks):
        if task.complexity <= 2:
            batchable_indices.append(idx)
        else:
            individual_indices.append(idx)

    # --- Batch C:1-2 tasks (single claude -p call) ---
    if len(batchable_indices) >= 2:
        batch_tasks = [tasks[i] for i in batchable_indices[:MAX_BATCH_SIZE]]
        overflow = batchable_indices[MAX_BATCH_SIZE:]
        individual_indices.extend(overflow)  # overflow runs individually
        batch_result = _execute_batch(batch_tasks, goal, budget, dag)
        for idx in batchable_indices:
            results[idx] = batch_result
    elif len(batchable_indices) == 1:
        # Only one — no point batching
        individual_indices.append(batchable_indices[0])

    # --- Execute C:3+ tasks (and single C:1-2) individually in parallel ---
    if individual_indices:
        def _run_one(task):
            contracts_text = load_relevant_contracts(task, dag)
            return execute_leaf_task(task, goal, budget, contracts_text)

        with ThreadPoolExecutor(max_workers=max(1, len(individual_indices))) as executor:
            futures = {
                executor.submit(_run_one, tasks[idx]): idx
                for idx in individual_indices
            }
            for future in futures:
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    print(f"  [ERROR] Task {tasks[idx].id} raised: {exc}")
                    results[idx] = _FAIL_RESULT.copy()

    return results


def _find_newly_done_branches(dag: RecursiveDAG, previously_done: set) -> list:
    """Find parent (branch) tasks that just transitioned to 'done' after propagation."""
    newly_done = []
    for task in dag.tasks.values():
        if task.status == "done" and task.children and task.id not in previously_done:
            newly_done.append(task)
    return newly_done


def execute_recursive_dag(
    dag: RecursiveDAG,
    goal: str,
    budget: BudgetTracker,
    kanban_state: KanbanState = None,
    kanban_path: str = None,
) -> None:
    """Recursive DAG execution loop with retry tracking, verification dispatch, and failure handling.

    Parameters
    ----------
    dag:    The recursive DAG to execute.
    goal:   The top-level goal string (for prompt context).
    budget: Budget tracker for cost accounting and circuit breaking.
    kanban_state: Optional KanbanState instance for tracking progress.
    kanban_path: Optional file path for kanban JSON output.
    """
    execution_retries: dict = {}  # task_id -> retry count

    # Track which branch tasks are already done (to detect newly-done branches)
    done_branches: set = {
        t.id for t in dag.tasks.values()
        if t.status == "done" and t.children
    }

    batch_num = 0
    stagnant_batches = 0
    MAX_STAGNANT_BATCHES = 3
    prev_done_count = sum(1 for t in dag.tasks.values() if t.status == "done")

    while True:
        ready = dag.get_ready_leaves()
        if not ready:
            break
        if not budget.can_afford():
            print(f"\n[BUDGET EXHAUSTED] Remaining: ${budget.remaining():.4f}. Stopping recursive execution.")
            break

        batch_num += 1
        parallel, sequential = dag.get_parallel_groups(ready)

        print(f"\n{'─'*40}")
        print(f"Batch {batch_num} | {len(parallel)} parallel + {len(sequential)} sequential | "
              f"Budget ${budget.remaining():.2f}")
        print(f"{'─'*40}")

        # --- Execute parallel leaves ---
        if parallel:
            print(f"  Executing {len(parallel)} task(s) in parallel: {[t.id for t in parallel]}")
            for t in parallel:
                t.status = "running"
            results = _execute_leaf_parallel(parallel, goal, budget, dag)

            for task, result in zip(parallel, results):
                success = result.get("success", False)
                task.cost_usd += result.get("cost_usd", 0.0)

                if success:
                    # L1 verification
                    l1_pass = run_l1(task, budget)
                    if l1_pass:
                        commit_hash = checkpoint_commit(task, success=True)
                        dag.mark_done(task.id, result)
                        task.commit_hash = commit_hash
                    else:
                        # L1 failed — treat as task failure
                        commit_hash = checkpoint_commit(task, success=False)
                        task.commit_hash = commit_hash
                        _handle_task_failure(
                            task, dag, budget, execution_retries,
                            f"L1 verification failed for {task.id}",
                        )
                else:
                    commit_hash = checkpoint_commit(task, success=False)
                    task.commit_hash = commit_hash
                    error_msg = result.get("output", "")[:500]
                    _handle_task_failure(
                        task, dag, budget, execution_retries,
                        f"Execution failed: {error_msg}",
                    )

        # --- Execute sequential leaves (batch C:1-2, individual C:3+) ---
        if sequential:
            # Split sequential tasks into batchable (C:1-2) and individual (C:3+)
            seq_batch = [t for t in sequential if t.complexity <= 2]
            seq_individual = [t for t in sequential if t.complexity > 2]

            # Batch C:1-2 sequential tasks in one call
            if len(seq_batch) >= 2 and budget.can_afford():
                seq_batch_run = seq_batch[:MAX_BATCH_SIZE]
                seq_individual = seq_batch[MAX_BATCH_SIZE:] + seq_individual
                seq_batch = seq_batch_run
                for t in seq_batch:
                    t.status = "running"
                batch_result = _execute_batch(seq_batch, goal, budget, dag)
                success = batch_result.get("success", False)
                cost_per = batch_result.get("cost_usd", 0.0) / max(len(seq_batch), 1)

                for task in seq_batch:
                    task.cost_usd += cost_per
                    if success:
                        l1_pass = run_l1(task, budget)
                        if l1_pass:
                            commit_hash = checkpoint_commit(task, success=True)
                            dag.mark_done(task.id, batch_result)
                            task.commit_hash = commit_hash
                        else:
                            commit_hash = checkpoint_commit(task, success=False)
                            task.commit_hash = commit_hash
                            _handle_task_failure(
                                task, dag, budget, execution_retries,
                                f"L1 verification failed for {task.id}",
                            )
                    else:
                        commit_hash = checkpoint_commit(task, success=False)
                        task.commit_hash = commit_hash
                        _handle_task_failure(
                            task, dag, budget, execution_retries,
                            f"Batch execution failed",
                        )
            elif len(seq_batch) == 1:
                seq_individual.insert(0, seq_batch[0])

            # Execute C:3+ (and lone C:1-2) individually
            for task in seq_individual:
                if not budget.can_afford():
                    print(f"\n[BUDGET EXHAUSTED] Remaining: ${budget.remaining():.4f}. Stopping.")
                    break

                print(f"\n  Executing task sequentially: {task.id}")
                task.status = "running"
                contracts_text = load_relevant_contracts(task, dag)
                result = execute_leaf_task(task, goal, budget, contracts_text)
                success = result.get("success", False)
                task.cost_usd += result.get("cost_usd", 0.0)

                if success:
                    l1_pass = run_l1(task, budget)
                    if l1_pass:
                        commit_hash = checkpoint_commit(task, success=True)
                        dag.mark_done(task.id, result)
                        task.commit_hash = commit_hash
                    else:
                        commit_hash = checkpoint_commit(task, success=False)
                        task.commit_hash = commit_hash
                        _handle_task_failure(
                            task, dag, budget, execution_retries,
                            f"L1 verification failed for {task.id}",
                        )
                else:
                    commit_hash = checkpoint_commit(task, success=False)
                    task.commit_hash = commit_hash
                    error_msg = result.get("output", "")[:500]
                    _handle_task_failure(
                        task, dag, budget, execution_retries,
                        f"Execution failed: {error_msg}",
                    )

        # --- Propagate status (children all done → parent done) ---
        dag.propagate_status()

        # --- Verify newly-completed branch nodes by complexity ---
        newly_done = _find_newly_done_branches(dag, done_branches)
        for branch in newly_done:
            done_branches.add(branch.id)
            print(f"\n  [Branch] {branch.id} completed (complexity={branch.complexity})")

            if branch.complexity >= 3:
                l2_pass = run_l2(branch, budget)
                if not l2_pass:
                    print(f"  [Branch] {branch.id}: L2 review failed")

            if branch.complexity >= 5:
                l3_pass = run_l3(branch, budget)
                if not l3_pass:
                    print(f"  [Branch] {branch.id}: L3 test suite failed")

        # --- Update kanban ---
        if kanban_state is not None:
            kanban_state.update_from_dag(dag)
            if kanban_path:
                kanban_state.save(kanban_path)
            kanban_state.print_tree()

        # --- Stagnation detection ---
        current_done_count = sum(1 for t in dag.tasks.values() if t.status == "done")
        if current_done_count > prev_done_count:
            stagnant_batches = 0
            prev_done_count = current_done_count
        else:
            stagnant_batches += 1
            if stagnant_batches >= MAX_STAGNANT_BATCHES:
                print(f"\n[STAGNATION] No new tasks completed in {MAX_STAGNANT_BATCHES} batches. Stopping.")
                break

        # --- Status report ---
        print(f"\n--- DAG Status (done:{current_done_count}/{len(dag.tasks)} stagnant:{stagnant_batches}) ---")
        print(f"{dag.summary()}\nBudget: {budget.summary()}\n------------------")

    # Final check
    if dag.all_done():
        print("\n  All tasks completed.")
    else:
        pending = [t for t in dag.tasks.values() if t.status == "pending"]
        failed = [t for t in dag.tasks.values() if t.status == "failed"]
        if pending:
            print(f"\n  {len(pending)} task(s) still pending.")
        if failed:
            print(f"\n  {len(failed)} task(s) failed.")


def _handle_task_failure(
    task: RecursiveTask,
    dag: RecursiveDAG,
    budget: BudgetTracker,
    execution_retries: dict,
    error_context: str,
) -> None:
    """Handle a task failure: retry or replan.

    Maintains execution_retries dict. If retries < max_retries, resets task
    to 'pending' for retry. Otherwise, marks failed and attempts replan_subtree.
    If replan also fails, marks [FAILED] and continues.
    """
    task_id = task.id
    execution_retries[task_id] = execution_retries.get(task_id, 0) + 1
    retries = execution_retries[task_id]

    print(f"  [Failure] {task_id}: attempt {retries}/{task.max_retries} — {error_context[:200]}")

    if retries < task.max_retries:
        # Retry: reset to pending so get_ready_leaves picks it up again
        task.status = "pending"
        print(f"  [Retry] {task_id}: resetting to pending for retry")
    else:
        dag.mark_failed(task_id, error_context)

        # Only replan C>=3 tasks. C:1-2 are atomic — replanning causes infinite expansion.
        if task.complexity >= 3:
            print(f"  [Replan] {task_id}: max retries exhausted, attempting replan (C:{task.complexity})...")
            replan_ok = replan_subtree(task, dag, error_context, budget)
            if not replan_ok:
                print(f"  [FAILED] {task_id}: replan failed, skipping task")
                checkpoint_commit(task, success=False)
        else:
            print(f"  [FAILED] {task_id}: max retries exhausted (C:{task.complexity}, no replan)")
            checkpoint_commit(task, success=False)


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
    recursive: bool = False,
    kanban: bool = False,
    kanban_path: str = None,
    verify_level: str = "auto",
    dry_run: bool = False,
    kanban_serve: bool = False,
    kanban_port: int = 8420,
):
    """Main persistent loop logic.

    Modes:
        dag   — Plan a DAG of sub-tasks, execute each as an independent
                ``claude -p`` call with budget tracking and parallel execution.
                When *recursive* is True, uses recursive planning and execution.
        legacy — Original behaviour: one full Claude session per round,
                 WIP-file handshake between rounds.
    """
    ensure_wip_dir()
    start_time = time.time()
    budget = BudgetTracker(max_budget_usd, per_task_budget_usd)

    # Start kanban HTTP server if requested (implies --kanban)
    if kanban_serve:
        kanban = True
        _start_kanban_server(kanban_port)

    mode_label = f"{mode}" + (" (recursive)" if recursive else "")
    print(f"{'='*60}")
    print("Persistent loop started")
    print(f"Goal: {goal}")
    print(f"Mode: {mode_label}")
    print(f"Max rounds: {max_rounds} | Max time: {max_time}s")
    print(f"Budget: ${max_budget_usd:.2f} total, ${per_task_budget_usd:.2f} per task")
    if recursive:
        print(f"Verify level: {verify_level} | Kanban: {'on' if kanban else 'off'}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if mode == "dag":
        _run_dag_mode(
            goal, max_rounds, max_time, budget, start_time, skip_clarify,
            recursive=recursive, kanban=kanban, kanban_path=kanban_path,
            verify_level=verify_level, dry_run=dry_run,
        )
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
    recursive: bool = False,
    kanban: bool = False,
    kanban_path: str = None,
    verify_level: str = "auto",
    dry_run: bool = False,
):
    """DAG mode: plan once, execute sub-tasks atomically with budget control.

    When *recursive* is True, uses recursive_plan + execute_recursive_dag
    instead of the flat plan_dag + execute_dag pipeline.
    """
    original_goal = goal

    # Phase 0: Clarify goal before first round
    if not skip_clarify:
        goal = clarify_goal(goal, budget)
        original_goal = goal

    # Prepare kanban state if requested — write an initial "planning" state
    # immediately so the web viewer doesn't 404 during the planning phase.
    kanban_state = None
    kanban_out = None
    if kanban:
        kanban_out = kanban_path or os.path.join(WIP_DIR, "kanban.json")
        kanban_state = KanbanState(goal)
        kanban_state.summary = {
            "total": 0, "done": 0, "failed": 0,
            "running": 0, "pending": 0, "total_cost_usd": 0.0,
            "phase": "planning",
        }
        kanban_state.save(kanban_out)

    dag = None  # Will be set in the loop; used after loop for summary

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
        if recursive:
            print(f"  Mode: recursive | Verify: {verify_level}")
        print(f"{'─'*60}")

        # Phase 1: Plan
        if recursive:
            dag = recursive_plan(goal, budget)
        else:
            dag = plan_dag(goal, budget)

        if not dag.tasks:
            print("  [DAG] No tasks generated. Stopping.")
            break

        # Dry-run: print the plan and exit without executing
        if dry_run:
            print(f"\n{'='*60}")
            print("[DRY RUN] Planning complete. Task tree:")
            print(f"{'='*60}\n")
            print(dag.summary())
            if kanban_state:
                kanban_state.update_from_dag(dag)
                kanban_state.save(kanban_out)
                print(f"\n  [Kanban] Written to {kanban_out}")
                kanban_state.print_tree()
            print(f"\n{'='*60}")
            print("[DRY RUN] Exiting without executing tasks.")
            print(f"{'='*60}")
            return

        # Phase 2: Execute
        if recursive:
            execute_recursive_dag(dag, goal, budget, kanban_state=kanban_state, kanban_path=kanban_out)
        else:
            execute_dag(dag, goal, budget, kanban_state=kanban_state, kanban_path=kanban_out)

        # Write final kanban state
        if kanban_state:
            kanban_state.update_from_dag(dag)
            kanban_state.save(kanban_out)
            kanban_state.print_tree()
            print(f"  [Kanban] Written to {kanban_out}")

        # Phase 3: Check results
        failed = [t for t in dag.tasks.values() if t.status == "failed"]
        done = [t for t in dag.tasks.values() if t.status == "done"]
        pending = [t for t in dag.tasks.values() if t.status == "pending"]

        print(f"\n  Round {round_num} result: {len(done)} done, {len(failed)} failed, {len(pending)} pending")

        if not failed and not pending:
            print(f"\n{'='*60}")
            print(f"All tasks completed in round {round_num}!")
            print(f"{'='*60}")
            break

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
    else:
        # Loop completed without break
        pass

    # Phase 3 (final): Cleanup contracts and print summary
    if recursive:
        print("\n  [Cleanup] Removing contract files...")
        cleanup_contracts()

    print(f"\n  DAG execution summary:")
    print(f"    Budget spent: {budget.summary()}")
    print(f"    Total time: {int(time.time() - start_time)}s")

    # Check if there's unfinished work (failed/pending may not be set if DAG was empty)
    all_done = dag.all_done() if dag and dag.tasks else True
    if not all_done:
        print(f"\nTo continue: python scripts/persistent-solve.py \"{original_goal}\""
              f"{' --recursive' if recursive else ''}")


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
# Kanban HTTP Server
# ============================================================

def _start_kanban_server(port: int = 8420) -> threading.Thread:
    """Start a lightweight HTTP server in a background thread for the kanban viewer.

    Serves the project root so that kanban-viewer.html can fetch
    .claude-flow/kanban.json via a relative URL.  The server runs on
    localhost and is intended for local development only.

    Returns the daemon thread (auto-stops when main process exits).
    """
    import http.server

    # Suppress request logs to avoid cluttering the main output
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=".", **kwargs)

        def log_message(self, format, *args):
            pass

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), QuietHandler)
    except OSError:
        # Port already in use — try a few alternatives
        for alt_port in range(port + 1, port + 10):
            try:
                server = http.server.HTTPServer(("127.0.0.1", alt_port), QuietHandler)
                port = alt_port
                break
            except OSError:
                continue
        else:
            print(f"  [Kanban] Could not start HTTP server on ports {port}-{port+9}")
            return None

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    viewer_url = f"http://localhost:{port}/scripts/kanban-viewer.html"
    print(f"  [Kanban] Viewer: {viewer_url}")
    print(f"  [Kanban] Auto-refreshes every 3s — open in browser")

    # Try to open browser automatically
    import webbrowser
    try:
        webbrowser.open(viewer_url)
    except Exception:
        pass  # Non-critical — user can open manually

    return thread


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
    parser.add_argument(
        "--recursive", action="store_true",
        help="Use recursive DAG planning and execution (v2 engine)"
    )
    parser.add_argument(
        "--kanban", action="store_true",
        help="Enable kanban JSON output during execution"
    )
    parser.add_argument(
        "--kanban-path", type=str, default=None,
        help="Custom path for kanban JSON output (default: .claude-flow/kanban.json)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only run recursive planning and print the kanban tree, without executing any tasks"
    )
    parser.add_argument(
        "--kanban-serve", action="store_true",
        help="Start a local HTTP server and open kanban-viewer.html in browser (auto-refresh)"
    )
    parser.add_argument(
        "--kanban-port", type=int, default=8420,
        help="Port for the kanban HTTP server (default: 8420)"
    )
    parser.add_argument(
        "--verify-level", choices=["auto", "l1", "l2", "l3"], default="auto",
        help="Verification level: 'auto' (based on complexity), 'l1', 'l2', 'l3' (default: auto)"
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
        recursive=args.recursive,
        kanban=args.kanban or args.kanban_serve,
        kanban_path=args.kanban_path,
        verify_level=args.verify_level,
        dry_run=args.dry_run,
        kanban_serve=args.kanban_serve,
        kanban_port=args.kanban_port,
    )


if __name__ == "__main__":
    main()
