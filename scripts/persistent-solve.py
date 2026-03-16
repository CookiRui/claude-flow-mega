#!/usr/bin/env python3
"""
Persistent Loop Scheduler — Never stop until the goal is achieved.

Usage:
    python scripts/persistent-solve.py "Stabilize game frame rate at 60fps"
    python scripts/persistent-solve.py "Refactor user auth system" --max-rounds 5
    python scripts/persistent-solve.py "Fix memory leak" --max-time 1800

How it works:
    1. Launches a Claude Code session to pursue the goal
    2. When session budget runs out, checks WIP for progress
    3. If goal not achieved, automatically starts a new session resuming from WIP
    4. Repeats until goal is achieved or circuit breaker triggers
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# Circuit Breaker Thresholds
# ============================================================
DEFAULT_MAX_ROUNDS = 10
DEFAULT_MAX_TIME = 3600      # 1 hour
DEFAULT_MAX_COST = 5.0       # $5 (reserved, cannot track precisely yet)
MAX_CONSECUTIVE_NO_PROGRESS = 3
MAX_SAME_ERROR = 3

# ============================================================
# Core Logic
# ============================================================

def run_claude_session(prompt: str, timeout: int = 1800) -> str:
    """Launch a Claude Code session and return its output."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
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


def build_first_round_prompt(goal: str) -> str:
    """Build the prompt for round 1: fresh task."""
    return f"""{goal}

Important instructions:
- This is round 1 of a persistent loop. Push the goal as far as possible before budget runs out.
- If budget is about to run out and goal is not complete, save WIP (work-in-progress), including:
  round: 1, auto_resume: true, completed tasks, remaining DAG, strategies tried, exit reason.
- If the goal is achieved, include this marker at the end of output: [GOAL_ACHIEVED]
- If a problem requires human decision (very low confidence), include: [NEED_HUMAN]
- If stuck, try self-rescue first (change approach / decompose finer / deep search) before giving up."""


def build_resume_prompt(goal: str, round_num: int) -> str:
    """Build the prompt for subsequent rounds: resume from WIP."""
    return f"""Resume WIP.

This is round {round_num} of an automatic persistent loop. Original goal: {goal}

Resume progress from WIP and continue pushing toward the goal until achieved or budget exhausted.
- Do NOT repeat completed work. Start from the "next steps" in WIP.
- If the goal is achieved, include this marker at the end of output: [GOAL_ACHIEVED]
- If human decision is needed, include: [NEED_HUMAN]
- When budget is about to run out, save WIP with round: {round_num}
- If stuck, try self-rescue (change approach / decompose finer / deep search) before giving up."""


def check_output(output: str) -> str:
    """Analyze output to determine status."""
    if "[GOAL_ACHIEVED]" in output:
        return "achieved"
    if "[NEED_HUMAN]" in output:
        return "need_human"
    if "[TIMEOUT]" in output:
        return "timeout"
    return "continue"


def estimate_progress(output: str, prev_output: str) -> bool:
    """Rough check: did the session make progress? (output significantly different)"""
    if not prev_output:
        return True
    # Simple heuristic: output length differs by > 10% or content differs
    if abs(len(output) - len(prev_output)) > len(prev_output) * 0.1:
        return True
    return output != prev_output


def persistent_solve(goal: str, max_rounds: int, max_time: int):
    """Main persistent loop logic."""
    start_time = time.time()
    history = []
    prev_output = ""
    no_progress_count = 0

    print(f"{'='*60}")
    print(f"Persistent loop started")
    print(f"Goal: {goal}")
    print(f"Max rounds: {max_rounds}")
    print(f"Max time: {max_time}s")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

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
        session_timeout = min(1800, remaining_time)  # Max 30 min per round

        print(f"\n{'─'*60}")
        print(f"Round {round_num}/{max_rounds} | "
              f"Elapsed {int(elapsed)}s | "
              f"Remaining {remaining_time}s")
        print(f"{'─'*60}")

        # Build prompt
        if round_num == 1:
            prompt = build_first_round_prompt(goal)
        else:
            prompt = build_resume_prompt(goal, round_num)

        # Execute
        output = run_claude_session(prompt, timeout=session_timeout)
        status = check_output(output)

        # Record history
        history.append({
            "round": round_num,
            "status": status,
            "time": time.time() - start_time,
            "output_length": len(output)
        })

        # Progress detection
        if estimate_progress(output, prev_output):
            no_progress_count = 0
        else:
            no_progress_count += 1
            print(f"  [WARNING] No visible progress this round ({no_progress_count} consecutive)")

        prev_output = output

        # Status handling
        if status == "achieved":
            print(f"\n{'='*60}")
            print(f"Goal achieved in round {round_num}!")
            print(f"Total time: {int(time.time() - start_time)}s")
            print(f"{'='*60}")
            return

        if status == "need_human":
            print(f"\n{'='*60}")
            print(f"Round {round_num} requires human decision. Pausing loop.")
            print(f"Check WIP files for details. Resume with 'Resume WIP' when ready.")
            print(f"{'='*60}")
            return

        if status == "timeout":
            print(f"  Round timed out. WIP may not be saved. Will attempt recovery next round.")

        # Normal end, short pause before next round
        print(f"  Round ended ({status}). Preparing next round...")
        time.sleep(3)

    # Loop finished
    print(f"\n{'='*60}")
    print(f"Persistent loop ended")
    print(f"Total rounds: {len(history)}")
    print(f"Total time: {int(time.time() - start_time)}s")
    print(f"Final status: Goal not achieved — check WIP files to continue manually")
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
