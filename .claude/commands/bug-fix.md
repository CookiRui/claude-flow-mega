---
description: Diagnose and fix bugs, solidify learnings into Rules/Skills/Memory
argument-hint: <bug description>
---

# /bug-fix

## Phase 1: Diagnosis — Hypothesis-Verification Loop (NO code writing)

### Step 1: Collect Evidence

1. Understand bug symptoms (user description + logs + repro steps). If info insufficient, use AskUserQuestion
2. Locate relevant code (search -> read -> understand call chain -> load related Skills)
3. **Gather observable facts** — do NOT jump to conclusions. Record:
   - What is the actual behavior?
   - What is the expected behavior?
   - Under what conditions does it reproduce?
   - What has changed recently? (`git log --oneline -10`)

### Step 2: Form Hypotheses

Based on evidence, form **2-3 ranked hypotheses** (most likely first):

```
Hypothesis 1 (most likely): {description} — because {evidence}
Hypothesis 2: {description} — because {evidence}
Hypothesis 3: {description} — because {evidence}
```

### Step 3: Verify Hypotheses

For each hypothesis, starting with the most likely:
1. **Design a verification step** — a read, grep, or trace that would confirm or eliminate this hypothesis
2. **Execute** — run the verification (read code, check logs, trace data flow)
3. **Record result** — CONFIRMED / ELIMINATED / INCONCLUSIVE
4. If CONFIRMED -> proceed to root cause analysis. If all ELIMINATED -> go back to Step 2 with new evidence.

**Anti-pattern:** Never skip to "I think it's X, let me fix it" without verification. Evidence first.

### Step 4: Root Cause Analysis

Output:
   - **Symptom**: What the user sees
   - **Verified hypothesis**: Which hypothesis was confirmed and how
   - **Direct cause**: Which code causes it
   - **Root cause**: Why (knowledge gap / pattern violation / missing check / timing / data / config / third-party)
   - **Impact scope**: Where else similar issues may exist
   - **Fix proposal**: Minimal change — what to change and why
   - **Solidification needed?**: Whether to add Rule / update Skill / write Memory

### Step 5: Confirm with user

**Must wait for user confirmation via AskUserQuestion — never skip this**

## Phase 2: Fix (after user confirms)

1. Read before modifying, minimal change principle
2. **Write regression test first** (RED) — Reproduce the bug with a test, confirm it fails
3. Fix the code (GREEN) — Make the regression test pass
4. Constitution compliance audit

## Phase 3: Pre-Completion Verification

Execute the full `verification` skill checklist:
- All existing tests + new regression test pass
- Constitution compliance checked article by article
- Impact scope confirmed (do similar issues exist elsewhere?)

## Phase 4: Solidify (as needed)

Based on Phase 1 assessment:
- Add Rule → `.claude/rules/`
- Update Skill → `.claude/skills/`
- Write Memory → `MEMORY.md`
- Output fix summary (Bug → Root cause → Fix → Regression test → Prevention)

## Prohibited Actions

- Do not modify code without understanding the bug
- Do not skip user confirmation
- Do not skip regression testing
- Do not opportunistically refactor code around the bug
- Do not delete code that "looks unused" without confirmation
- Do not declare "fix complete" before all verification checks PASS
