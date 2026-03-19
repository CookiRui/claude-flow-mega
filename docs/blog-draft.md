# I Stopped Babysitting Claude Code — Here's the 4-Layer System That Made It Work

> Claude Code is powerful, but without structure it forgets your architecture, violates your conventions, and writes code you'd never approve. Here's how I fixed that.

---

## The Problem

Every Claude Code session, I played the same game: re-explain our architecture, catch the same violations, clean up the same mess. I manage a game project with strict performance constraints and a custom framework — and Claude's default behavior was almost always wrong.

Every time I started a Claude Code session, the same things happened:

- **It forgot our architecture.** We use a custom `ManagerCenter` for dependency injection — Claude kept using `new` directly.
- **It violated performance rules.** No allocations in hot paths is sacred to us — Claude happily wrote `new List<>()` inside `Update()`.
- **It used the wrong libraries.** We have a custom logging wrapper — Claude defaulted to `Debug.Log`.
- **It couldn't handle complex tasks.** A cross-module refactor would start well, then lose context halfway through and produce inconsistent code.

I tried writing a long `CLAUDE.md` file. It helped for small tasks, but for anything involving multiple files, Claude still drifted.

The issue isn't length — it's that a flat file has no priority hierarchy. Claude treats every line equally. A rule about variable naming gets the same weight as "never allocate in Update()". What I needed wasn't more rules — it was a way to signal which ones are non-negotiable.

## The Solution: 4 Layers of Progressive Disclosure

The insight was simple: **not all context needs to be loaded all the time.** A flat CLAUDE.md forces everything into every conversation, wasting tokens and diluting important rules.

I built a 4-layer config system:

```
Layer 1: Constitution  — Always loaded. 4-7 non-negotiable rules.
Layer 2: Rules         — Always loaded. Coding style supplements.
Layer 3: Skills        — On-demand. Loaded only when task matches trigger.
Layer 4: Commands      — User-invoked. Complex workflows with multiple phases.
```

### Layer 1: Constitution (the "laws" Claude must never break)

Only things AI would get wrong without being told. Each rule has a paired correct/wrong code example:

```markdown
## §1: All systems register through ManagerCenter

​```csharp
// Correct
ManagerCenter.Register<IAuthService>(new AuthService());

// Wrong — Claude's default behavior
var auth = new AuthService();
​```
```

**The filter**: If you remove a rule and Claude's default behavior is still correct, delete it. I got my 20+ rule CLAUDE.md down to 5 constitution articles.

### Layer 2: Rules (coding style details)

Supplements the constitution with patterns that aren't architectural constraints but still matter:

```markdown
## Rule 1: Prefer Span<T> over array copies in hot paths (per Constitution §3)
```

Rules supplement the constitution with style-level details — things that aren't architecture violations but still matter for consistency. Keeping them separate lets you update conventions without touching the constitutional rules.

### Layer 3: Skills (on-demand reference docs)

This is the token saver. Skills are only loaded when Claude recognizes it needs them:

```markdown
---
name: custom-networking
description: "Custom UDP networking layer. Use when working with multiplayer, packets, or NetManager."
---
```

Claude reads the trigger description. If the task involves networking, it loads the skill. If not, it costs zero tokens.

### Layer 4: Commands (complex workflows)

Reusable multi-phase workflows:

- `/init-project` — AI auto-analyzes your codebase and generates all 4 layers
- `/deep-task <goal>` — 8-layer autonomous engine for complex tasks
- `/bug-fix <description>` — Diagnosis → regression test → fix → learning capture

`/bug-fix` is worth noting: it forces a regression test *before* the fix, so you verify the fix actually addresses the root cause, not just the symptom.

## The Autonomous Engine: `/deep-task`

The config system solved the "Claude does the wrong thing" problem. But complex tasks still had issues:

- Claude would lose context halfway through a large refactor
- No verification — it would declare "done" with broken tests
- No learning — the same mistakes repeated across sessions

So I built an 8-layer execution engine on top:

```
Phase 0: Classify complexity (S/M/L/XL)
Phase 1: Goal review — is this feasible? Clear enough?
Phase 2: DAG decomposition — break into sub-tasks with dependencies
Phase 3: Parallel execution — non-conflicting tasks run simultaneously
Phase 4: 3-level verification:
         L1: Self-check per task
         L2: Reviewer ↔ Executor adversarial loop (up to 3 rounds)
         L3: End-to-end integration test
Phase 5: Meta-learning — record what worked for next time
```

Phase 0 is key: not every task needs all 8 phases — S-class tasks (single file, auto-verifiable) skip straight to execution and commit. Phase 5 writes findings to your project's `learnings.md`, so the system gets better the more you use it.

### The key insight: Reviewer ↔ Executor convergence

Most "code review" prompts are one-shot: "review this diff." The problem is the reviewer finds issues but nobody fixes them.

My L2 verification is a **loop**:

```
Reviewer Agent → finds issues → Executor Agent fixes them →
Reviewer re-reviews → still issues? → Executor fixes again →
Reviewer approves (or escalates after 3 rounds)
```

This catches real bugs. In my first test (upgrading the persistent-solve.py script), the L2 reviewer found:

- A thread-safety bug in the budget tracker (missing lock) — `total_spent += cost` isn't atomic, so parallel tasks could corrupt the running total
- An exception handling gap that would crash parallel execution — one failing `future.result()` silently dropped all remaining parallel results, then the caller crashed on `None`
- A default value (`is_error: true`) that silently marked every successful response as failed

All three would have shipped if I'd skipped L2.

## The Atomic DAG Scheduler: Real Budget Control

Claude Code sessions have no cost visibility. You don't know how much a task costs until the bill arrives.

I discovered that `claude -p --output-format json` returns actual cost data:

```json
{
  "total_cost_usd": 0.0537,
  "usage": { "input_tokens": 8698, "output_tokens": 4 },
  "duration_ms": 4078
}
```

So I built a scheduler that decomposes goals into sub-tasks, executes each as an independent `claude -p` call, and tracks costs:

```bash
python scripts/persistent-solve.py "Refactor auth system" --max-budget-usd 3.0

# Output:
# Final budget summary:
#   Total spent: $1.2345 / $3.00
#     planning: $0.0800
#     task-1: $0.3200
#     task-2: $0.4500
#     task-3: $0.3845
#   Total time: 342s
```

Non-conflicting sub-tasks run in parallel. Budget circuit-breakers stop execution before you overspend.

## Results

I've used this across 4 projects over 3 months — a game engine, two backend services, and a client codebase I didn't write. Here are the numbers:

| Metric | Before | After |
|--------|--------|-------|
| Constitution violations per session | ~3-5 | <1 avg (constitution anchors behavior) |
| "Done" but actually broken | ~30% | <5% (L2 catches most) |
| Context loss on large tasks | Frequent | Rare (DAG + checkpoints) |
| Cost visibility | None | Per-task tracking |
| Setup time for new project | 30-60 min | 3 min (`/init-project`) |

The biggest win isn't any single number — it's **trust**. I now delegate L-level tasks (cross-module refactors, new subsystems) to Claude Code and review the output, instead of hand-holding every step.

## Try It

```bash
npx claude-autosolve init
```

Or clone directly: `git clone https://github.com/CookiRui/claude-flow.git && python install.py`

Then in Claude Code:

```
/init-project
```

AI analyzes your project and generates all configuration automatically. No placeholders to fill.

The whole framework is open source: [github.com/CookiRui/claude-flow](https://github.com/CookiRui/claude-flow)

---

*Built by a game developer who got tired of Claude forgetting the same rules every session.*
