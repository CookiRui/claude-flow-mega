---
description: Diagnose and fix bugs, solidify learnings into Rules/Skills/Memory
argument-hint: <bug description>
---

# /bug-fix

## Phase 1: Diagnosis (NO code writing)

1. Understand bug symptoms (user description + logs + repro steps). If info is insufficient, use AskUserQuestion
2. Locate relevant code (search -> read -> understand call chain -> load related Skills)
3. Output root cause analysis report:
   - **Symptom**: What the user sees
   - **Direct cause**: Which line of code causes it
   - **Root cause**: Why this code was written (knowledge gap / pattern violation / missing check / timing issue / data issue / config issue / third-party / requirement mismatch)
   - **Impact scope**: Where else might similar issues exist
   - **Fix proposal**: Minimal change fix — what to change and why
   - **Solidification needed?**: Whether to add Rule / update Skill / write Memory
4. **Must wait for user confirmation via AskUserQuestion — never skip this**

## Phase 2: Fix (after user confirms)

1. Read before modifying, minimal change principle
2. **Write regression test first** (RED) — Reproduce the bug with a test, confirm test fails
3. Fix the code (GREEN) — Make the regression test pass
4. Constitution compliance audit

## Phase 3: Pre-Completion Verification

Execute the full `verification` skill checklist:
- All existing tests + new regression test pass
- Constitution compliance checked article by article
- Impact scope confirmed (do similar issues exist elsewhere?)

## Phase 4: Solidify (as needed)

Based on Phase 1 assessment, execute:
- Add Rule -> `.claude/rules/`
- Update Skill -> `.claude/skills/`
- Write Memory -> `MEMORY.md`
- Output fix summary (Bug -> Root cause -> Fix -> Regression test -> Prevention)

## Subagent Constraints

If subagents are dispatched during the fix:
- Subagents **must** first read `.claude/constitution.md`
- Code fixed by subagents **must** pass `verification` skill

## Prohibited Actions

- Do not modify code without understanding the bug
- Do not skip user confirmation
- Do not skip regression testing and go straight to fixing
- Do not opportunistically refactor code around the bug
- Do not delete code that "looks unused" without confirmation
- Do not guess the behavior of code you haven't read
- Do not declare "fix complete" before all verification checks PASS
