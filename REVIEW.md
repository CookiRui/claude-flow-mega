# Code Review Standards — claude-flow

> Review criteria for automated and human reviewers.

---

## Review Dimensions & Severity Levels

| Severity | Label | Merge Policy |
|---|---|---|
| BLOCKER | Must be resolved before merge |
| WARNING | Should be resolved; acceptable with written justification |
| SUGGESTION | Optional improvement; no merge gate |

---

## Dimension A: Performance

Not applicable — claude-flow is a template distribution framework with no runtime hot paths. Skip performance review unless changes touch `persistent-solve.py`'s parallel execution or `repo-map.py`'s file scanning.

| ID | Severity | Rule |
|---|---|---|
| PERF-W1 | WARNING | `repo-map.py` file scanning should skip directories in the ignore list early, not after reading |
| PERF-W2 | WARNING | `persistent-solve.py` ThreadPoolExecutor must not spawn unbounded threads |

---

## Dimension B: Maintainability

| ID | Severity | Rule |
|---|---|---|
| MAINT-B1 | BLOCKER | template/ files must preserve `{placeholder}` format — never replace with concrete values | Constitution §1 |
| MAINT-B2 | BLOCKER | README.md must match template/ structure after any template file change | Constitution §2 |
| MAINT-B3 | BLOCKER | Each commit must be atomic: one logical change | `.claude/rules/git-workflow.md` |
| MAINT-W1 | WARNING | When modifying `.claude/commands/X.md`, the parallel `template/.claude/commands/X.md` must also be updated | `.claude/rules/coding-style.md` |
| MAINT-W2 | WARNING | Python scripts must follow the unified entry point format (argparse + main) | Constitution §3 |
| MAINT-W3 | WARNING | Magic literals must be named constants |
| MAINT-S1 | SUGGESTION | Test names should describe behavior: `test_returns_empty_list_when_input_is_null` |

---

## Dimension C: Correctness & Security

| ID | Severity | Rule |
|---|---|---|
| SEC-B1 | BLOCKER | No hardcoded secrets, tokens, passwords, or API keys |
| SEC-B2 | BLOCKER | Python scripts must use stdlib only — no external dependencies | Constitution §3 |
| SEC-B3 | BLOCKER | Errors must not be silently swallowed; every except must log or re-raise |
| SEC-W1 | WARNING | `persistent-solve.py` shared state (BudgetTracker) must use threading.Lock |
| SEC-W2 | WARNING | subprocess calls must use list form, not shell=True with string interpolation |
| SEC-W3 | WARNING | New npm/Python dependencies require explicit justification |
| SEC-S1 | SUGGESTION | Consider adding property-based tests for DAG parsing logic |

---

## Review Output Format

```
## Review: {PR-or-commit-id} — {short-description}

**Reviewer:** {reviewer-name}
**Overall verdict:** APPROVED | APPROVED WITH CONDITIONS | BLOCKED

---

### BLOCKERS (must fix before merge)
- [ ] [MAINT-B1] <file>:<line> — <description>

### WARNINGS (should fix or justify)
- [ ] [MAINT-W1] <file>:<line> — <description>

### SUGGESTIONS (optional)
- [ ] [SEC-S1] <file>:<line> — <description>

---

### Summary
<1-3 sentence summary>
```

---

## References

- Constitution: `.claude/constitution.md`
- Coding style: `.claude/rules/coding-style.md`
- Git workflow: `.claude/rules/git-workflow.md`
- Security: `.claude/rules/security.md`
- Issue tracker: https://github.com/CookiRui/claude-flow/issues
- Dependency manifest: `package.json`
