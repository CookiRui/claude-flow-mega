---
name: {skill-name}
description: "{framework/module} usage guide: {keyword-1}, {keyword-2}, {keyword-3}. Use when working with {scenario-1}, {scenario-2}, {scenario-3}."
---

<!--
  The trigger description is the most critical part of a Skill — it determines when AI loads it.

  ❌ Vague (won't trigger):
  description: "network conventions"

  ✅ Precise (triggers accurately):
  description: "Network communication: HTTP requests, Socket connections, Protobuf messaging, reconnection. Use when working with network requests, message sending/receiving, reconnection, network error handling."

  Formula: "{topic}: {keyword-1}, {keyword-2}, {keyword-3}. Use when working with {scenario-1}, {scenario-2}, {scenario-3}."
-->

# {Skill Name}

<!--
  Optional: If this Skill defines a mandatory methodology (e.g., TDD, verification),
  add an enforcement declaration. Framework/API Skills typically don't need this.

## Enforcement Declaration

This Skill applies to {applicable-scenarios}. **This is not a suggestion — it is mandatory.**
Only exception: {exception-scenarios}.
-->

## Component Reference

| Component    | Responsibility |
|--------------|----------------|
| {component-1} | {description}  |
| {component-2} | {description}  |

<!-- Component table omits file paths (AI can search). Reduces token overhead. -->

## Core Usage

### {usage-1-name}

```{language}
// ✅ Correct
{correct-approach}

// ❌ Wrong
{wrong-approach}
```

### {usage-2-name}

```{language}
// ✅ Correct
{correct-approach}
```

## Common Pitfalls

1. {pitfall-1} -> {consequence}. Fix: {solution}
2. {pitfall-2} -> {consequence}. Fix: {solution}

@references/detail.md
