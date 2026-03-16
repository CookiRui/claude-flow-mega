---
description: Analyze requirements and generate a technical plan
argument-hint: <feature-name>
---

# /feature-plan-creator

## Phase 1: Requirements Confirmation (NO code writing)

1. Read constitution (`.claude/constitution.md`) + relevant design docs (`Docs/`)
2. Conduct 2-3 rounds of requirements clarification via AskUserQuestion:
   - Round 1: Feature goals, user scenarios, core interactions
   - Round 2: Data model, integration with existing systems, performance requirements
   - Round 3 (if needed): Edge cases, MVP scope
3. Summarize approach in 1-2 paragraphs, **must wait for user confirmation before Phase 2**

## Phase 2: Generate Technical Plan

Output `Docs/{feature-name}/plan.md` with these sections:

1. **Overview** — Feature description, goals, non-goals
2. **Affected Modules** — List of modules to create/modify
3. **Data Model** — Key data structures
4. **Flow Design** — Main flow (step-by-step) + error flows
5. **{component-1} Design** — Module responsibilities, interface definitions
6. **{component-2} Design** — Module responsibilities, interface definitions
7. **Test Plan** — TDD cycle list (see granularity constraints below)
8. **Constitution Compliance Audit** — Check against constitution article by article

<!-- Adjust sections by project type:
  - Game projects: add Manager design, event design, asset requirements, performance considerations
  - Web projects: add API design, frontend components, state management
  - Backend projects: add database changes, error codes, deployment impact
-->

## Phase 3: Task Breakdown (Granularity Constraints)

Break the technical plan into a **micro-task list**. Each task must satisfy:

1. **Time <= 5 minutes** — If over 5 minutes, granularity is too coarse, keep splitting
2. **Target files explicit** — Each task specifies files to create/modify
3. **Verifiable** — Each task has a clear "done criteria" (tests pass / compiles / observable behavior)
4. **TDD marked** — Tasks involving functional code tagged `[TDD]`, must follow RED-GREEN-REFACTOR

Format:
```markdown
### Micro-task List

- [ ] [TDD] Implement XXX logic -> `{file-path}` | Done: XXX test passes
- [ ] [TDD] Implement YYY interface -> `{file-path}` | Done: YYY test passes
- [ ] Configure ZZZ -> `{file-path}` | Done: compiles successfully
```

## Subagent Constraints

If subagents are dispatched during execution:
- Subagents **must** first read `.claude/constitution.md` and task-relevant Skills
- Subagent output **must** pass `verification` skill before merging
- Each subagent task includes a status report: `DONE` | `DONE_WITH_CONCERNS` | `BLOCKED`

## Prohibited Actions

- Do not generate technical plans with unclear requirements
- Do not skip user confirmation steps
- Do not introduce patterns forbidden by the constitution
- Do not add features beyond MVP scope
- Do not generate tasks with granularity over 5 minutes
