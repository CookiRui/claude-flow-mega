---
description: Diagnose and fix bugs, solidify learnings into Rules/Skills/Memory
argument-hint: <bug description>
---

# /bug-fix

## Phase 1: Diagnosis (NO code writing)

1. Understand bug symptoms (user description + logs + repro steps). If info insufficient, use AskUserQuestion
2. Locate relevant code (search → read → understand call chain → load related Skills)
3. Output root cause analysis:
   - **Symptom**: What the user sees
   - **Direct cause**: Which code causes it
   - **Root cause**: Why (knowledge gap / pattern violation / missing check / timing / data / config / third-party)
   - **Impact scope**: Where else similar issues may exist
   - **Fix proposal**: Minimal change — what to change and why
   - **Solidification needed?**: Whether to add Rule / update Skill / write Memory
4. **Must wait for user confirmation via AskUserQuestion — never skip this**

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
