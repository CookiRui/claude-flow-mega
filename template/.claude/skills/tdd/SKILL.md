---
name: tdd
description: "TDD development: test-driven development, RED-GREEN-REFACTOR, unit tests, integration tests. Use when implementing new features, refactoring code, verifying bug fixes, or writing tests."
---

# TDD — Test-Driven Development

## Enforcement Declaration

This Skill applies to all new feature development and refactoring tasks. **This is not a suggestion — it is mandatory.** If a task involves functional code changes, you must follow the RED-GREEN-REFACTOR cycle. Only exception: pure configuration/asset/documentation changes.

## RED-GREEN-REFACTOR Cycle

Each feature point must follow this sequence. **No skipping steps**:

### 1. RED — Write a Failing Test First

```
// Before writing ANY implementation code:
1. Write test cases based on requirements (cover happy path + at least 1 edge case)
2. Run tests -> confirm they fail (RED)
3. If tests pass immediately -> test is flawed, reconsider
```

### 2. GREEN — Minimal Implementation to Pass

```
// Write just enough code to make all tests green:
1. Implement the minimum code to pass all tests
2. Do NOT add functionality not covered by tests
3. Do NOT optimize prematurely
```

### 3. REFACTOR — Improve While Keeping Green

```
// Only refactor after all tests are green:
1. Eliminate duplicate code
2. Improve naming and structure
3. Run tests after each refactoring step -> must stay green
4. Refactoring must not change external behavior
```

## Granularity Control

- Each RED-GREEN-REFACTOR cycle covers **one behavior point**, not an entire feature
- One feature = multiple cycles, each cycle < 5 minutes
- If a cycle takes > 10 minutes -> granularity is too coarse, split further

## Adapt to Your Project Type

<!--
  Uncomment the section matching your project:

  Unity games:
  - Pure logic -> EditMode Test (fast, no scene needed)
  - MonoBehaviour/Scene/Physics -> PlayMode Test
  - Network/Persistence -> Integration Test

  Web frontend:
  - Component rendering -> React Testing Library
  - Business logic -> Jest unit tests
  - User flows -> Playwright E2E

  Backend services:
  - Business logic -> Unit tests (mock external deps)
  - API endpoints -> Integration tests (real database)
  - Cross-service -> Contract tests
-->

## Anti-patterns

1. **Write implementation first, add tests later** -> Tests become rubber stamps proving existing code works, not driving design
2. **Tests only cover happy path** -> Edge cases explode in production
3. **Add new features during REFACTOR phase** -> Conflates change scope, can't isolate test failure causes
4. **Skip RED confirmation** -> Without confirming tests can fail, you don't know if they're actually testing what you intend
