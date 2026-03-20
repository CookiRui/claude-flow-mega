# Project Constitution

This file **only defines project-specific, counter-intuitive constraints that AI wouldn't know**.

> **Inclusion criteria**: If you remove a rule, will AI's default behavior produce incorrect code? Yes -> keep it; No -> remove it.

---

## §1: {core-architecture-constraint}

<!-- Your most critical architectural pattern. Example: "All systems register through ManagerCenter, never instantiate directly" -->

{One-line description}. See `{skill-name}` skill for details.

```{language}
// ✅ Correct
{correct-code}

// ❌ Wrong
{wrong-code}
```

---

## §2: {communication-data-flow-constraint}

<!-- How do modules communicate? Example: "Inter-module communication only through EventCenter, no cross-module direct references" -->

{One-line description}

- {rule-1}
- {rule-2}

---

## §3: {performance-resource-constraint}

<!-- Performance red lines. Delete this section for non-performance-critical projects. Example: "No allocations in hot paths" -->

{One-line description}

- {rule-1}
- {rule-2}
- Rules above apply to hot paths only; cold paths prioritize readability

---

## §4: {tech-stack-constraint}

<!-- "Must use X instead of Y" — AI tends to use what it's most familiar with. -->

- **Non-negotiable**: {must-use-X, never-use-Y}
- **Non-negotiable**: {must-use-X, never-use-Y}

<!-- Add §5-§7 as needed. Recommended total: 4-7 articles. -->

---

## Governance

This constitution has the highest priority, superseding any `CLAUDE.md` or single-session instructions.

### Enforcement Protocol

The following clauses are non-negotiable:

1. **Skill mandatory loading** — When a task matches a Skill's trigger conditions, the Skill must be loaded and followed.
2. **Subagent constraint inheritance** — Subagents must first read `constitution.md` and relevant Skills before execution. Subagent output must pass `verification` skill before merging.
3. **Confirmation gates cannot be skipped** — Steps marked "must wait for user confirmation" in Commands must not be skipped.
4. **Pre-completion verification** — Before declaring any feature or bug fix "complete", the `verification` skill checklist must be executed.
5. **Violation handling** — If committed code violates the constitution, immediately flag and fix it.
6. **Skill semantic matching** — Skills are triggered not only by keywords but by task semantics. When a task involves adding or modifying functional behavior → load `tdd`. When a task is about to be declared complete → load `verification`. Judge by what the task *does*, not just what words the user used.
