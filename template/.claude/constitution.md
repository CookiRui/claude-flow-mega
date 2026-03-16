# Project Constitution

This file **only defines project-specific, counter-intuitive constraints that AI wouldn't know**.
Common programming wisdom (YAGNI, no empty catches, comment the "why") does NOT belong here — AI already knows these.

> **Inclusion criteria**: If you remove a rule, will AI's default behavior produce incorrect code? Yes -> keep it; No -> remove it.

---

## Article 1: {core-architecture-constraint}

<!--
  Fill-in guide: Your project's most critical architectural pattern. AI will produce structurally wrong code without it.
  Examples:
  - Game client: "All systems register through ManagerCenter, never instantiate managers directly"
  - Backend: "All concurrency through Actor message passing, no raw goroutines or shared memory"
  - Web frontend: "State management only via Zustand, no props drilling beyond 2 levels"
-->

{One-line description of your architecture rule}. See `{skill-name}` skill for details.

```{language}
// ✅ Correct
{correct-code}

// ❌ Wrong
{wrong-code}
```

<!-- Every article should have ✅/❌ paired code examples — 10x more effective than plain text rules -->

---

## Article 2: {communication-data-flow-constraint}

<!--
  How do modules communicate? AI will directly import classes across modules by default.
  Examples:
  - "Inter-module communication only through EventCenter, no cross-module direct references"
  - "All API requests through Repository layer, no direct database calls"
-->

{One-line description}

- {rule-1}
- {rule-2}

---

## Article 3: {performance-resource-constraint}

<!--
  What are your performance red lines? What pitfalls does "normal" AI code create?
  Delete this article for non-performance-critical projects (scripts, tools, etc).
  Examples:
  - Games: "No allocations in hot paths: no new, no boxing, no string concat; use object pools"
  - Backend: "Single request < 100ms, no file IO in request chain"
-->

{One-line description}

- {rule-1}
- {rule-2}
- Rules above apply to hot paths only; cold paths prioritize readability

---

## Article 4: {tech-stack-constraint}

<!--
  "Must use X instead of Y" — AI tends to use what it's most familiar with.
  Examples:
  - "Async must use UniTask, no Coroutine/Task"
  - "Logging must use MLog, no Debug.Log"
  - "HTTP client must use project's HttpService wrapper, no raw fetch"
-->

- **Non-negotiable**: {must-use-X, never-use-Y}
- **Non-negotiable**: {must-use-X, never-use-Y}

<!--
  Add Articles 5-7 as needed. Recommended total: 4-7 articles. More than 7 and AI won't remember them all.

  High-value references:
  - Networked games: protocol specification (message format, layered architecture)
  - Microservices: inter-service communication (gRPC/HTTP, retry policies)
  - Data-intensive: data consistency (transaction boundaries, idempotency)
-->

---

## Governance

This constitution has the highest priority, superseding any `CLAUDE.md` or single-session instructions.

### Enforcement Protocol

The following clauses are non-negotiable and must never be skipped, simplified, or deferred:

1. **Skill mandatory loading** — When a task matches a Skill's trigger conditions, the Skill must be loaded and followed. There is no "skip it this time" option.
2. **Subagent constraint inheritance** — When dispatching subagents, they must first read `constitution.md` and relevant Skills, inheriting the same constraints as the parent agent.
3. **Confirmation gates cannot be skipped** — Steps marked "must wait for user confirmation" in Commands must not be skipped, even if the user urges speed.
4. **Pre-completion verification** — Before declaring any feature or bug fix "complete", the `verification` skill checklist must be executed. No "good enough" shortcuts.
5. **Violation handling** — If committed code violates the constitution, immediately flag and fix it. "Already written" is not an excuse to keep violating code.
