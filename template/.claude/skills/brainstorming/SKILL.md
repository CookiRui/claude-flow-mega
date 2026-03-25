# Brainstorming Skill

Design exploration and requirements refinement: idea generation, requirements clarification, trade-off analysis. Use when starting a new feature, exploring design alternatives, or when requirements are vague or conflicting.

## When to Use

- Before `/feature-plan-creator` — to refine vague requirements into concrete specs
- When the user says "I want to build X" but scope/approach is unclear
- When multiple design approaches exist and trade-offs need evaluation
- When requirements conflict or have implicit assumptions

## Socratic Refinement Process

### Round 1: Problem Understanding

Ask questions to understand the **why** before the **what**:

1. **What problem does this solve?** — Not "what feature do you want" but "what pain are you addressing?"
2. **Who is affected?** — Users, developers, CI, other systems?
3. **What does success look like?** — Observable outcome, not implementation detail
4. **What are the constraints?** — Time, compatibility, performance, dependencies

Output a **Problem Statement** (2-3 sentences). Ask user to confirm before continuing.

### Round 2: Solution Exploration

Generate **2-3 distinct approaches** with trade-offs:

```markdown
### Approach A: {name}
- **How**: {1-2 sentence description}
- **Pros**: {list}
- **Cons**: {list}
- **Complexity**: S / M / L
- **Risk**: {main risk}

### Approach B: {name}
...

### Approach C: {name}
...
```

Ask the user: "Which approach resonates? Or should we explore a hybrid?"

### Round 3: Detail Refinement

For the chosen approach, drill into specifics:

1. **Scope boundaries** — What is explicitly IN and OUT of scope?
2. **Edge cases** — What happens when {unusual input}? When {system is down}? When {concurrent access}?
3. **Integration points** — Which existing modules are touched? What APIs change?
4. **Data model** — What new types/schemas are needed?
5. **Migration** — Is there existing data/behavior to preserve?

Output a **Design Brief** that can be directly fed to `/feature-plan-creator`.

## Design Brief Format

```markdown
## Design Brief: {feature-name}

### Problem
{problem statement from Round 1}

### Chosen Approach
{approach name and description from Round 2}

### Scope
- **In scope**: {list}
- **Out of scope**: {list}

### Key Decisions
- {decision-1}: {rationale}
- {decision-2}: {rationale}

### Edge Cases Identified
- {edge-case-1}: {handling strategy}
- {edge-case-2}: {handling strategy}

### Integration Points
- {module-1}: {what changes}
- {module-2}: {what changes}

### Open Questions
- {question-1} (if any remain)
```

## Anti-patterns

- **Do NOT** skip to implementation details in Round 1 — understand the problem first
- **Do NOT** present only one approach — always offer alternatives for comparison
- **Do NOT** make assumptions — ask if unsure
- **Do NOT** generate code during brainstorming — this is a design-only phase
- **Do NOT** spend more than 3 rounds — if still unclear, summarize what's known and flag open questions
