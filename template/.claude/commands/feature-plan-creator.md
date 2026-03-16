---
description: Analyze requirements and generate a technical plan
argument-hint: <feature-name>
---

# /feature-plan-creator

## Phase 1: Requirements Confirmation (NO code writing)

1. Read constitution (`.claude/constitution.md`) + relevant design docs
2. Clarify requirements via AskUserQuestion (2-3 rounds: goals & scenarios → data model & integration → edge cases)
3. Summarize approach in 1-2 paragraphs, **must wait for user confirmation before Phase 2**

## Phase 2: Generate Technical Plan

Output `Docs/{feature-name}/plan.md`:

1. **Overview** — Goals, non-goals
2. **Affected Modules** — Modules to create/modify
3. **Data Model** — Key data structures
4. **Flow Design** — Main flow + error flows
5. **Module Design** — Responsibilities, interface definitions (add sections per module)
6. **Test Plan** — TDD cycle list (see granularity constraints below)
7. **Constitution Compliance Audit** — Check against constitution article by article

## Phase 3: Task Breakdown

Break the plan into a **micro-task list**. Each task must satisfy:

1. **Time ≤ 5 minutes** — If over, keep splitting
2. **Target files explicit** — Each task specifies files to create/modify
3. **Verifiable** — Clear done criteria (tests pass / compiles / observable behavior)
4. **TDD marked** — Functional code tasks tagged `[TDD]`, must follow RED-GREEN-REFACTOR

```markdown
### Micro-task List

- [ ] [TDD] Implement XXX logic -> `{file-path}` | Done: XXX test passes
- [ ] [TDD] Implement YYY interface -> `{file-path}` | Done: YYY test passes
- [ ] Configure ZZZ -> `{file-path}` | Done: compiles successfully
```

## Prohibited Actions

- Do not generate plans with unclear requirements
- Do not skip user confirmation steps
- Do not introduce patterns forbidden by the constitution
- Do not add features beyond MVP scope
- Do not generate tasks with granularity over 5 minutes
