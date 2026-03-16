---
name: verification
description: "Pre-completion verification: code submission checks, feature completion validation, bug fix confirmation, constitution compliance audit. Use when a task is about to complete, code is ready to commit, or declaring a feature done."
---

# Verification — Pre-Completion Checks

## Enforcement Declaration

**Before declaring any feature or bug fix "complete", this checklist must pass.** No "good enough", "main flow works", or "minor issues can be fixed later". If any check fails, task status is "in progress", not "complete".

## Verification Checklist

Check items in order. Each must be explicitly PASS / FAIL / N/A:

### 1. Feature Completeness

- [ ] All feature points from requirements/plan are implemented
- [ ] No TODO/FIXME/HACK comments left in committed code (resolve or convert to Issues before commit)
- [ ] Edge cases handled (nulls, extreme inputs, concurrency scenarios)

### 2. Test Verification

- [ ] All existing tests pass (zero failures, zero skipped)
- [ ] New features have corresponding test coverage
- [ ] Manual verification of main flow + at least 1 edge case

### 3. Constitution Compliance

- [ ] Checked against `constitution.md` article by article, no violations
- [ ] Tech stack choices match constitution mandates (async framework, logging, communication, etc.)
- [ ] No performance violations in hot paths (if applicable)

### 4. Code Quality

- [ ] No compiler warnings (or confirmed as unrelated)
- [ ] New code follows `rules/coding-style.md`
- [ ] No unnecessary dependencies introduced

### 5. Impact Scope

- [ ] Changes don't affect unrelated modules (check import changes)
- [ ] Configuration file changes documented
- [ ] If public interfaces modified -> callers already updated

## Handling Failures

```
Check item FAIL?
├── Missing feature -> implement, re-run verification
├── Test failure -> fix code or test, never skip/delete failing tests
├── Constitution violation -> fix immediately, "already written" is not an excuse
└── Scope larger than expected -> notify user, evaluate whether to rollback
```

## Output Format

After verification, output a summary:

```markdown
## Verification Result

| Check Item            | Result | Notes          |
|-----------------------|--------|----------------|
| Feature Completeness  | PASS   |                |
| Test Verification     | PASS   | 3 new tests    |
| Constitution Compliance | PASS |                |
| Code Quality          | PASS   |                |
| Impact Scope          | PASS   |                |

✅ Verification passed. Ready to commit.
```
