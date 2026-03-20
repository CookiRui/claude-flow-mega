---
description: Autonomous 8-layer deep execution engine for complex tasks
argument-hint: <goal description>
---

# /deep-task

Autonomous execution engine. Classifies complexity, decomposes into DAG, executes in parallel with Agent tool, verifies at three levels, and captures learnings.

## Phase 0: Complexity Classification

Classify the goal before doing anything else:

| Question | Yes | No |
|----------|-----|----|
| Only 1 file, no dependencies, auto-verifiable? | → **S** | ↓ |
| 2-5 files, clear acceptance criteria? | → **M** | ↓ |
| Cross-module or architecture decision? | → **L** | ↓ |
| Needs product/strategic judgment? | → **XL** | Use L |

Output your classification and reasoning.

### S — Fast Path

1. Execute directly
2. L1 self-check
3. `git commit -m "checkpoint: {description}"`
4. **Done. Stop here.**

### M — Standard Path

1. Decompose into 2-5 linear sub-tasks, each with acceptance criteria
2. Execute sequentially:
   - Execute sub-task
   - `git commit -m "checkpoint: {task}"`
   - L1 self-check
3. L2 verification on critical path (if any)
4. **Done. Stop here.**

### L/XL — Full Engine (continue to Phase 1)

---

## Phase 1: Goal Review (NO code changes)

1. **Check for existing WIP**: Read `.claude-flow/wip.md`. If it exists and matches this goal, resume from Phase 3 with the existing DAG.

2. **Goal Clarity Gate** (L/XL tasks are complex enough to warrant this):
   - Is the scope clear (what's included / excluded)?
   - Can you determine when this is "done"?
   - Are there ambiguous terms or requirements?

   | Confidence | Action |
   |-----------|--------|
   | ≥ 0.8 | Proceed |
   | 0.5–0.8 | State assumptions, notify user, proceed |
   | < 0.5 | `AskUserQuestion` with questions + default assumptions. **Wait for response.** |

3. **Assess feasibility**:
   - Is the goal physically possible?
   - Are there hidden tradeoffs? If yes → notify user.
   - Confidence < 0.3 → present options and let user decide direction.

4. **Build context**:
   - Read constitution (`.claude/constitution.md`)
   - Run `python scripts/repo-map.py --format md --no-refs` if available (generates code map)
   - Load relevant Skills

5. **Read historical learnings**: Read `.claude-flow/learnings.md` if it exists.
   - Extract pitfalls relevant to this task's domain (e.g., same module, same type of change)
   - Add as explicit constraints to Phase 2 decomposition ("avoid X because it failed before")
   - If a previous task of the same type succeeded, reuse its strategy as the default approach

6. **Plan model routing**:
   - Editing/simple tasks → `Agent(model="haiku")`
   - Search/analysis tasks → `Agent(model="sonnet")`
   - Architecture decisions → keep in main context (current model)

7. Output: refined goal statement + feasibility assessment + learnings constraints.
   - **XL only**: `AskUserQuestion` — must wait for user confirmation before Phase 2.

---

## Phase 2: DAG Decomposition

Break the goal into a DAG (Directed Acyclic Graph) of sub-tasks.

Each sub-task must have:
- **ID**: short identifier (e.g., `T1`, `T2a`)
- **Description**: what to do
- **Acceptance criteria**: machine-verifiable condition (test passes / compiles / behavior observable)
- **Dependencies**: list of task IDs that must complete first
- **Model**: `haiku` (edits), `sonnet` (analysis), or `main` (architecture)
- **Files**: which files to create/modify

Format:
```
- T1: Set up data models → `src/models.py` | Done: types defined, imports work | Deps: none | Model: haiku
- T2: Implement core logic → `src/service.py` | Done: unit tests pass | Deps: T1 | Model: sonnet
- T3: Add API endpoint → `src/routes.py` | Done: endpoint responds | Deps: T2 | Model: haiku
- T4: Integration tests → `tests/` | Done: all tests pass | Deps: T2, T3 | Model: sonnet
```

### Decomposition Pre-Check

Before proceeding, verify:
- [ ] **Coverage**: all sub-tasks done = original goal achieved?
- [ ] **Independence**: boundaries between tasks are clear?
- [ ] **Verifiable**: each acceptance criterion can be checked automatically?
- [ ] **Granularity**: each task ≤ 5 minutes? If not, split further.
- [ ] **Dependencies**: DAG is acyclic and correctly ordered?

**XL tasks**: present DAG via `AskUserQuestion`, must wait for confirmation.

---

## Phase 3: Parallel Execution Loop

```
while ready_tasks exist:
    1. Get ready tasks (all dependencies met)
    2. Group by conflict (tasks touching same files = conflict)
    3. Non-conflicting → launch in PARALLEL via multiple Agent() calls in ONE message
    4. Conflicting → execute SEQUENTIALLY
    5. After each batch:
       a. Verify completed tasks (L1)
       b. Run regression check on previously completed tasks
       c. git commit -m "checkpoint: {task-id} {description}"
       d. If regression fails → git revert → replan with constraint
       e. Update DAG status
```

### Agent Call Format

For each sub-task, launch:
```
Agent(
  model="{task.model}",
  prompt="Execute this task:\n{task.description}\n\nAcceptance criteria: {task.criteria}\n\nFiles to modify: {task.files}\n\nIMPORTANT:\n- Read the constitution first (.claude/constitution.md)\n- Follow TDD if this involves functional code\n- Only modify the specified files\n- Verify acceptance criteria before finishing"
)
```

Launch **multiple Agent calls in a single message** for parallel execution.

### Anti-Loop Rules

- Same strategy fails twice → MUST switch approach
- 3 consecutive failures on one task → escalate:
  - Confidence 0.3-0.5 → `AskUserQuestion` with 2-3 options
  - Confidence < 0.3 → save WIP, present full handoff

### Failure Salvage

When a sub-task fails, before discarding:
- What hypotheses were eliminated?
- What code/data is reusable?
- How does this narrow the solution space?

Record salvage in the DAG status for future attempts.

### Inter-Agent Signal Channel

When parallel Agents discover information that affects other tasks, use `.claude-flow/signals/` for lightweight communication:

```
.claude-flow/signals/
  {source-task}_to_{target-task}.md   # e.g., T1_to_T3.md
```

**Writing signals** (by executing Agent):
- Only write a signal when a discovery **changes the contract** between tasks (e.g., API signature changed, schema field renamed, dependency added)
- Signal format: one line summary + affected files + what the downstream task should do differently
- Do NOT signal style preferences or non-blocking observations

**Reading signals** (by main execution loop):
- After each parallel batch completes, check `.claude-flow/signals/` for new files
- If a signal targets a not-yet-started task, inject the signal content into that task's Agent prompt
- If a signal targets an already-completed task, flag for re-verification in L1
- Clean up signals after all tasks complete

This is a **best-effort** protocol — Agents that don't write signals are not in violation. The value is in catching interface-breaking changes early rather than discovering them in L2.

---

## Phase 4: Three-Level Verification

### Verification Level Selector

Before running verification, assess the **change impact** to avoid wasting budget on low-risk changes:

| Change Impact | Files Changed | Verification Level |
|--------------|---------------|-------------------|
| Docs / comments only | `*.md`, comments | L1 only — skip L2 and L3 |
| Tests only | test files only | L1 only — tests verify themselves |
| Config / infra | CI, settings, scripts | L1 + L3 (skip L2, go straight to full test suite) |
| Core logic (M task) | implementation files | L1 + L2-lite (1 round, no loop) + L3 |
| Core logic (L/XL task) | implementation files | L1 + L2-full (up to 3 rounds) + L3 |

Apply this selector **after Phase 3 completes**. Run `git diff --stat` to classify which category the actual changes fall into, regardless of original task complexity.

### L1 — Self-Check (during Phase 3, per sub-task)
Each Agent verifies its own acceptance criteria. Already done in execution loop.

### L2 — Multi-Agent Adversarial Loop (after all sub-tasks complete)

L2 is a **Reviewer ↔ Executor convergence loop**, not a one-shot review.

```
┌─ Reviewer Agent (sonnet) ◄───────────────┐
│  审查代码，提出问题清单                      │
│  输出: ISSUES [...] 或 PASS                 │
├─ PASS? ─── 是 → 进入 L3 ─────────────────→ 退出
│         └─ 否 ↓                             │
│  Executor Agent (sonnet)                    │
│  修复 Reviewer 提出的每个问题                │
│  git commit -m "fix: L2 review round N"     │
│                                             │
└─ 回到 Reviewer，重新审查 ────────────────────┘
   (最多 3 轮，第 3 轮仍有问题 → 升级给用户)
```

**Round 1 — Reviewer Agent:**
```
Agent(
  model="sonnet",
  prompt="You are a strict, independent code reviewer.

Review the following diff:
{git diff from start of /deep-task}

Check these dimensions:
1. Edge cases: are boundary conditions handled?
2. Assumptions: what implicit assumptions could break?
3. Integration: any risks with other modules?
4. Constitution: read .claude/constitution.md, check compliance article by article
5. Tests: are critical paths covered by tests?

Rules:
- Only flag REAL issues that could cause bugs or violate architecture. No style nitpicks.
- For each issue, specify: file, line, severity (critical/warning), what's wrong, how to fix.
- If everything looks good, output exactly: PASS

Output format:
ISSUES:
- [critical] file:line — description — suggested fix
- [warning] file:line — description — suggested fix
Or:
PASS"
)
```

**If ISSUES → Executor Agent:**
```
Agent(
  model="sonnet",
  prompt="Fix the following issues found by code review.
Do NOT argue with the reviewer — just fix each issue.
After fixing, run relevant tests to confirm.
git commit your fixes.

Issues to fix:
{reviewer's issue list}

Rules:
- Read .claude/constitution.md before making changes
- One commit per issue or group of related issues
- Run tests after fixing"
)
```

**Then back to Reviewer** with the updated diff. Repeat until PASS or 3 rounds.

**Round limit**: If Reviewer still reports issues after 3 rounds → `AskUserQuestion` with the remaining issues, let user decide whether to fix or accept.

### L2-Alt — Test Adversarial Loop (for critical paths)

For sub-tasks marked as critical, run an additional adversarial pattern:

```
┌─ Tester Agent ◄───────────────────┐
│  写边界测试和破坏性测试              │
│  输出: 新测试文件                   │
├─ 测试全过? ── 是 → 完成 ─────────→ 退出
│           └─ 否 ↓                  │
│  Executor Agent                    │
│  让失败的测试通过（不能删测试）      │
│  git commit                        │
│                                    │
└─ 回到 Tester，写更多边界测试 ───────┘
   (最多 3 轮)
```

**Tester Agent:**
```
Agent(
  model="sonnet",
  prompt="You are a QA engineer trying to BREAK this code.

Read the diff: {git diff}
Read the acceptance criteria: {original goal criteria}

Write tests that:
1. Test boundary values (0, -1, MAX, empty, null)
2. Test concurrent/race conditions (if applicable)
3. Test error paths (network failure, invalid input, disk full)
4. Test combinations the developer probably didn't think of

Do NOT write happy-path tests — those already exist.
Output: test files with descriptive names. Run them. Report which pass and which fail."
)
```

### L3 — End-to-End (final gate)
1. Run full test suite (including all tests from L2-Alt)
2. Check original goal's acceptance criteria
3. Constitution compliance audit (article by article)
4. If all pass → proceed to Phase 5
5. If fail → fix → re-verify from L2

---

## Phase 5: Meta-Learning

Analyze the execution trace and save insights:

1. What was the actual complexity vs. estimated? (Was S/M/L/XL correct?)
2. Which strategies worked? Which failed?
3. Any new patterns worth remembering?
4. How accurate were the time/effort estimates?

### 5.0 Cost Report

After all execution completes, output a cost summary to the user:

```
## Cost Report

| Category | Count | Est. Tokens (in/out) | Est. Cost |
|----------|-------|---------------------|-----------|
| Phase 3 Agents | {N} calls | {input}K / {output}K | ${amount} |
| L2 Review rounds | {N} rounds | {input}K / {output}K | ${amount} |
| L2-Alt Test rounds | {N} rounds | {input}K / {output}K | ${amount} |
| **Total** | | | **${total}** |

Model breakdown: haiku × {N}, sonnet × {N}, main context × 1
```

Estimation rules:
- Each Agent call ≈ 8K input + 2K output tokens (baseline)
- Add file content tokens: count lines read × 4 tokens/line
- Pricing: haiku $0.25/$1.25 per M, sonnet $3/$15 per M, opus $15/$75 per M
- This is a **rough estimate** — label it clearly as approximate

Also append the cost to the learnings entry (Phase 5.1) as:
```
- **Cost**: ~${total} ({N} agent calls: haiku × {N}, sonnet × {N})
```

### 5.1 Write to project: `.claude-flow/learnings.md`

This is the **project-level** learning log, visible to all team members and persisted in git.

If the file doesn't exist, create it with a header. Then **append** a new entry (never overwrite previous entries):

```markdown
## {date} — {goal summary}

- **Complexity**: estimated {X}, actual {Y}
- **Strategies that worked**: {list}
- **Strategies that failed**: {list with reasons}
- **Pitfalls discovered**: {list}
- **Verification notes**: L{N} was {sufficient/insufficient}, because {reason}
- **Time**: {rounds} rounds, {sub-tasks} sub-tasks
```

### 5.2 Write to Claude memory: `memory/meta_{domain}.md`

This is **Claude's private memory** for cross-project pattern matching. Write or update:

```markdown
---
name: meta_{domain}
description: Meta-strategy for {domain} tasks
type: feedback
---

## {Domain} Tasks

### Best Strategies
- {insight} (validated: {date})

### Pitfalls
- {what failed and why}

### Verification Level
- Recommend L{N}, because {reason}
```

If the file exists, update it. If not, create it.

### 5.3 Update project rules (if warranted)

If the execution revealed a constraint that the constitution or rules don't cover:
- New architectural constraint → propose addition to `.claude/constitution.md`
- New coding pattern → propose addition to `.claude/rules/`
- New framework usage pattern → propose new Skill in `.claude/skills/`

**Do not auto-modify these files** — output the proposed change and let the user decide via `AskUserQuestion`.

---

## Escalation Summary

| Confidence | Action |
|-----------|--------|
| > 0.8 | Proceed silently |
| 0.5–0.8 | Notify user of approach, continue |
| 0.3–0.5 | `AskUserQuestion` with 2-3 options |
| < 0.3 | Save WIP to `.claude-flow/wip.md`, full handoff |

---

## Prohibited Actions

- Do not skip Phase 0 complexity classification
- Do not run L/XL tasks through S/M fast path
- Do not use `Agent(model="opus")` for simple edits (cost waste)
- Do not skip L2 verification for L/XL tasks that touch core logic (use Verification Level Selector for exemptions)
- Do not commit without passing L1 check
- Do not proceed past XL decomposition without user confirmation
- Do not declare complete before L3 verification for L/XL tasks
- Do not repeat a failed strategy more than twice
