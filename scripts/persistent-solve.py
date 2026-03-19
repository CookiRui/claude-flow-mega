#!/usr/bin/env python3
"""
Persistent Loop Scheduler — Never stop until the goal is achieved.

Usage:
    python scripts/persistent-solve.py "Stabilize game frame rate at 60fps"
    python scripts/persistent-solve.py "Refactor user auth system" --max-rounds 5
    python scripts/persistent-solve.py "Fix memory leak" --max-time 1800

How it works:
    1. Launches a Claude Code session to pursue the goal
    2. Claude saves progress to .claude-flow/wip.md before budget runs out
    3. Script reads WIP file, injects it into next session's prompt
    4. Repeats until goal achieved or circuit breaker triggers

WIP handshake:
    - Script tells Claude: "Save WIP to .claude-flow/wip.md"
    - Claude writes WIP file with status/progress/next-steps
    - Script reads WIP file to determine status and inject context
    - This file is the ONLY communication channel between rounds
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ============================================================
# Constants
# ============================================================
DEFAULT_MAX_ROUNDS = 10
DEFAULT_MAX_TIME = 3600      # 1 hour
MAX_CONSECUTIVE_NO_PROGRESS = 3
WIP_DIR = ".claude-flow"
WIP_FILE = f"{WIP_DIR}/wip.md"

# ============================================================
# Budget Tracker
# ============================================================

class BudgetTracker:
    """Track cumulative costs across all claude sessions."""

    def __init__(self, max_budget_usd: float = 5.0, per_task_budget_usd: float = 0.5):
        self.max_budget = max_budget_usd
        self.per_task_budget = per_task_budget_usd
        self.total_spent = 0.0
        self.task_costs = {}  # task_id -> cost

    def record(self, task_id: str, cost_usd: float):
        """Record cost for a task."""
        self.total_spent += cost_usd
        self.task_costs[task_id] = self.task_costs.get(task_id, 0) + cost_usd

    def remaining(self) -> float:
        """Return remaining budget."""
        return max(0, self.max_budget - self.total_spent)

    def can_afford(self, estimated_cost: float = None) -> bool:
        """Check if we can afford another task."""
        if estimated_cost is None:
            estimated_cost = self.per_task_budget
        return self.remaining() >= estimated_cost * 0.1  # Allow if at least 10% of estimate remains

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


def read_wip() -> str | None:
    """Read WIP file content. Returns None if file doesn't exist."""
    try:
        with open(WIP_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def parse_wip_status(wip_content: str | None) -> str:
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


def count_completed_tasks(wip_content: str | None) -> int:
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

def run_claude_session(prompt: str, timeout: int = 1800) -> str:
    """Launch a Claude Code session and return its output."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text", "--dangerously-skip-permissions"],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        return result.stdout or ""
    except subprocess.TimeoutExpired:
        return "[TIMEOUT] Session timed out"
    except FileNotFoundError:
        print("Error: 'claude' command not found. Make sure Claude Code is installed and in PATH.")
        sys.exit(1)


# ============================================================
# Main Loop
# ============================================================

def persistent_solve(goal: str, max_rounds: int, max_time: int):
    """Main persistent loop logic."""
    ensure_wip_dir()
    start_time = time.time()
    prev_completed = 0
    no_progress_count = 0

    print(f"{'='*60}")
    print(f"Persistent loop started")
    print(f"Goal: {goal}")
    print(f"Max rounds: {max_rounds}")
    print(f"Max time: {max_time}s")
    print(f"WIP file: {os.path.abspath(WIP_FILE)}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    # Check if resuming from a previous run
    existing_wip = read_wip()
    if existing_wip:
        prev_completed = count_completed_tasks(existing_wip)
        print(f"\nFound existing WIP ({prev_completed} tasks completed). Resuming.")

    for round_num in range(1, max_rounds + 1):
        # Time circuit breaker
        elapsed = time.time() - start_time
        if elapsed >= max_time:
            print(f"\n[CIRCUIT BREAKER] Total time exceeded {max_time}s. Stopping.")
            break

        # No-progress circuit breaker
        if no_progress_count >= MAX_CONSECUTIVE_NO_PROGRESS:
            print(f"\n[CIRCUIT BREAKER] {MAX_CONSECUTIVE_NO_PROGRESS} consecutive rounds with no progress. Stopping.")
            break

        remaining_time = int(max_time - elapsed)
        session_timeout = min(1800, remaining_time)

        print(f"\n{'─'*60}")
        print(f"Round {round_num}/{max_rounds} | "
              f"Elapsed {int(elapsed)}s | "
              f"Remaining {remaining_time}s")
        print(f"{'─'*60}")

        # Build prompt — read WIP for context
        wip_content = read_wip()
        if round_num == 1 and not wip_content:
            prompt = build_first_round_prompt(goal)
        else:
            wip_content = wip_content or f"No WIP file found. Starting fresh on goal: {goal}"
            prompt = build_resume_prompt(goal, round_num, wip_content)

        # Execute
        output = run_claude_session(prompt, timeout=session_timeout)

        # Check WIP file for status (the real handshake)
        wip_after = read_wip()
        wip_status = parse_wip_status(wip_after)
        current_completed = count_completed_tasks(wip_after)

        # Progress detection — based on WIP completed tasks, not stdout
        if current_completed > prev_completed:
            no_progress_count = 0
            print(f"  Progress: {prev_completed} → {current_completed} tasks completed")
        elif wip_status == "done":
            no_progress_count = 0
        else:
            # Fallback: check if WIP content changed at all
            if wip_after and wip_after != wip_content:
                no_progress_count = 0
                print(f"  WIP updated (content changed)")
            else:
                no_progress_count += 1
                print(f"  [WARNING] No visible progress ({no_progress_count} consecutive)")

        prev_completed = current_completed

        # Status handling — based on WIP file, not stdout parsing
        if wip_status == "done":
            print(f"\n{'='*60}")
            print(f"Goal achieved in round {round_num}!")
            print(f"Total time: {int(time.time() - start_time)}s")
            print(f"Completed tasks: {current_completed}")
            print(f"{'='*60}")
            return

        if wip_status == "need_human":
            print(f"\n{'='*60}")
            print(f"Round {round_num} requires human decision.")
            print(f"Check {os.path.abspath(WIP_FILE)} for details.")
            print(f"After resolving, run this command again to continue.")
            print(f"{'='*60}")
            return

        if "[TIMEOUT]" in output:
            print(f"  Round timed out. WIP may not be saved.")

        # Also check stdout as fallback (Claude might not have written WIP)
        if "[GOAL_ACHIEVED]" in output and wip_status != "done":
            print(f"\n{'='*60}")
            print(f"Goal achieved in round {round_num} (detected from output)!")
            print(f"Total time: {int(time.time() - start_time)}s")
            print(f"{'='*60}")
            return

        print(f"  Round ended (WIP status: {wip_status}). Preparing next round...")
        time.sleep(3)

    # Loop finished without achieving goal
    print(f"\n{'='*60}")
    print(f"Persistent loop ended")
    print(f"Total rounds run: {min(round_num, max_rounds)}")
    print(f"Total time: {int(time.time() - start_time)}s")
    print(f"Completed tasks: {current_completed}")
    print(f"WIP saved at: {os.path.abspath(WIP_FILE)}")
    print(f"To continue: python scripts/persistent-solve.py \"{goal}\"")
    print(f"{'='*60}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Persistent Loop Scheduler — Never stop until the goal is achieved"
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

    args = parser.parse_args()
    persistent_solve(args.goal, args.max_rounds, args.max_time)


if __name__ == "__main__":
    main()
