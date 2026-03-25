# Code Review Standards — {project-name}

> This file defines the review criteria used by automated and human reviewers.
> Project-specific rules are marked with `{placeholder}` — fill them in during `npx claude-autosolve init`.

---

## Review Dimensions & Severity Levels

| Severity | Label | Merge Policy |
|---|---|---|
| 🔴 | **BLOCKER** | Must be resolved before merge |
| 🟡 | **WARNING** | Should be resolved; acceptable with written justification |
| 🔵 | **SUGGESTION** | Optional improvement; no merge gate |

---

## Code Tiers

Not all code deserves equal scrutiny. Apply review rules at the tier-appropriate severity.

| Tier | Paths | Description |
|------|-------|-------------|
| **Production** | `{production-paths}` | Core business logic, user-facing code — highest standards |
| **Tooling** | `{tooling-paths}` | Scripts, tests, dev tools, CI — relaxed performance rules |

### Tier Severity Override

| Rule Category | Production Tier | Tooling Tier |
|---------------|----------------|--------------|
| **A: Performance** | BLOCKER/WARNING as defined | All downgrade to **SUGGESTION** |
| **B: Maintainability** | WARNING/SUGGESTION as defined | **Unchanged** |
| **C: Correctness & Security** | BLOCKER/WARNING as defined | **Unchanged** |

> **Rationale:** Tooling code is executed infrequently and by developers only. Performance rules that are critical in production (e.g., no allocations in hot loops) are distracting noise in test/script code. However, correctness and maintainability matter everywhere.

---

## Dimension A: Performance

| ID | Severity | Rule | Example / Notes |
|---|---|---|---|
| PERF-B1 | BLOCKER | {performance-blocker-1} | e.g., no heap allocation inside hot-path loops |
| PERF-B2 | BLOCKER | {performance-blocker-2} | e.g., O(n²) or worse algorithm must carry an explanatory annotation |
| PERF-W1 | WARNING | {performance-warning-1} | e.g., repeated identical I/O calls should use a cache layer |
| PERF-W2 | WARNING | {performance-warning-2} | e.g., unbounded collection growth in long-lived objects |
| PERF-S1 | SUGGESTION | {performance-suggestion-1} | e.g., lazy initialization where startup cost matters |
| PERF-P1 | BLOCKER | No synchronous blocking call on the main/UI thread | Applies wherever {async-context} is relevant |
| PERF-P2 | WARNING | Resource handles (files, connections, sockets) must be released deterministically | Use language-idiomatic cleanup patterns |

> Add project-specific performance rules: `{performance-rule-project-specific}`

---

## Dimension B: Maintainability

| ID | Severity | Rule | Reference |
|---|---|---|---|
| MAINT-B1 | BLOCKER | All public APIs must have a docstring / header comment describing purpose, parameters, and return values | — |
| MAINT-B2 | BLOCKER | Each commit must be atomic: one logical change, all tests passing, build green | Constitution §{constitution-atomicity-section} |
| MAINT-B3 | BLOCKER | No dead code (commented-out blocks older than one sprint) without a dated TODO linking to an issue | — |
| MAINT-W1 | WARNING | Names must follow the convention defined in `.claude/rules/` | `.claude/rules/{naming-convention-file}` |
| MAINT-W2 | WARNING | Module boundaries must not be violated: `{module-A}` must not import from `{module-B}` | `.claude/constitution.md §{boundary-section}` |
| MAINT-W3 | WARNING | Functions exceeding {max-function-lines} lines should be decomposed unless justified | — |
| MAINT-W4 | WARNING | Magic literals must be named constants | — |
| MAINT-S1 | SUGGESTION | Consider extracting repeated logic (≥ 3 occurrences) into a shared helper | — |
| MAINT-S2 | SUGGESTION | Test names should describe behavior, not implementation | e.g., `test_returns_empty_list_when_input_is_null` |
| MAINT-P1 | BLOCKER | Constitution compliance: reviewer must confirm the change does not violate `.claude/constitution.md` | `.claude/constitution.md` |

> Add project-specific maintainability rules: `{maintainability-rule-project-specific}`

---

## Dimension C: Correctness & Security

| ID | Severity | Rule | Example / Notes |
|---|---|---|---|
| SEC-B1 | BLOCKER | No hardcoded secrets, tokens, passwords, or API keys | Use environment variables or a secrets manager |
| SEC-B2 | BLOCKER | All inputs crossing a trust boundary must be validated and sanitized | e.g., HTTP request params, file paths, IPC messages |
| SEC-B3 | BLOCKER | Errors must not be silently swallowed; every catch/except must log or re-raise | — |
| SEC-B4 | BLOCKER | Null / nil / undefined must be handled at every dereference that can receive it | — |
| SEC-W1 | WARNING | Shared mutable state accessed from multiple threads must use explicit synchronization | Document if single-threaded by design |
| SEC-W2 | WARNING | SQL / shell / eval construction using user data must use parameterized / escaped forms | — |
| SEC-W3 | WARNING | External dependencies added in this PR must be reviewed for license and supply-chain risk | Record in `{dependency-manifest}` |
| SEC-W4 | WARNING | {correctness-warning-project-specific} | e.g., schema version checks before migration |
| SEC-S1 | SUGGESTION | Consider adding a property-based or fuzz test for new parsing / serialization logic | — |
| SEC-S2 | SUGGESTION | {security-suggestion-project-specific} | e.g., rate-limit annotations on new endpoints |

> Add project-specific correctness/security rules: `{correctness-rule-project-specific}`

---

## Review Output Format

When submitting a code review (human or agent), use the following structure:

```
## Review: {PR-or-commit-id} — {short-description}

**Reviewer:** {reviewer-name}
**Date:** {review-date}
**Overall verdict:** APPROVED | APPROVED WITH CONDITIONS | BLOCKED

---

### BLOCKERS (must fix before merge)

- [ ] [PERF-B1] <file>:<line> — <description of violation>
- [ ] [SEC-B2] <file>:<line> — <description of violation>

### WARNINGS (should fix or justify)

- [ ] [MAINT-W3] <file>:<line> — <description> | **Justification:** <if deferring>

### SUGGESTIONS (optional)

- [ ] [MAINT-S1] <file>:<line> — <description>

---

### Summary

<1–3 sentence summary of the change and the main concerns.>

### Follow-up issues filed

- {issue-tracker-link-1}
- {issue-tracker-link-2}
```

---

## Project-Specific Additions

Fill in this section during project initialization or the first review cycle.

### Additional Performance Rules

| ID | Severity | Rule |
|---|---|---|
| PERF-X1 | {severity} | {project-perf-rule-1} |
| PERF-X2 | {severity} | {project-perf-rule-2} |

### Additional Maintainability Rules

| ID | Severity | Rule |
|---|---|---|
| MAINT-X1 | {severity} | {project-maintainability-rule-1} |
| MAINT-X2 | {severity} | {project-maintainability-rule-2} |

### Additional Correctness / Security Rules

| ID | Severity | Rule |
|---|---|---|
| SEC-X1 | {severity} | {project-correctness-rule-1} |
| SEC-X2 | {severity} | {project-correctness-rule-2} |

### Technology-Specific Checklist

> Replace `{language-or-framework}` with your stack and fill in relevant items.

**{language-or-framework} checklist:**

- [ ] {tech-specific-check-1}
- [ ] {tech-specific-check-2}
- [ ] {tech-specific-check-3}

---

## References

- Constitution: `.claude/constitution.md`
- Naming rules: `.claude/rules/{naming-convention-file}`
- Architecture diagram: `{architecture-doc-path}`
- Dependency manifest: `{dependency-manifest}`
- Issue tracker: `{issue-tracker-url}`
