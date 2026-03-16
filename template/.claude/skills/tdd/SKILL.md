---
name: tdd
description: "TDD development: test-driven development, RED-GREEN-REFACTOR, unit tests, integration tests. Use when implementing new features, refactoring code, verifying bug fixes, or writing tests."
---

# TDD — Test-Driven Development

## Enforcement Declaration

This Skill applies to all new feature development and refactoring tasks. **This is not a suggestion — it is mandatory.** Only exception: pure configuration/asset/documentation changes.

## RED-GREEN-REFACTOR Cycle

Each feature point must follow this sequence. **No skipping steps**:

| Phase | Steps |
|-------|-------|
| **RED** — Write failing test first | 1. Write test from requirements (happy path + ≥1 edge case) |
| | 2. Run tests → confirm RED |
| | 3. If tests pass immediately → test is flawed, reconsider |
| **GREEN** — Minimal implementation | 1. Write minimum code to pass all tests |
| | 2. No untested features, no premature optimization |
| **REFACTOR** — Improve while green | 1. Eliminate duplication, improve naming |
| | 2. Run tests after each step → must stay GREEN |
| | 3. Must not change external behavior |

## Granularity Control

- Each cycle covers **one behavior point**, not an entire feature
- One feature = multiple cycles, each cycle ≤ 5 minutes
- If a cycle takes > 10 minutes → split further

## Adapt to Your Project Type

<!--
  Uncomment the section matching your project:

  Unity games:
  - Pure logic -> EditMode Test | MonoBehaviour -> PlayMode Test | Network -> Integration Test

  Web frontend:
  - Components -> React Testing Library | Logic -> Jest | Flows -> Playwright E2E

  Backend services:
  - Logic -> Unit tests (mock external) | API -> Integration tests (real DB) | Cross-service -> Contract tests
-->

## Anti-patterns

1. **Write implementation first, add tests later** → Tests become rubber stamps, not design drivers
2. **Tests only cover happy path** → Edge cases explode in production
3. **Add features during REFACTOR** → Can't isolate test failure causes
4. **Skip RED confirmation** → You don't know if tests actually test what you intend
