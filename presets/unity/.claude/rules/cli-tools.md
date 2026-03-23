---
paths:
  - "**/*.sh"
  - "**/*.py"
  - "**/*.yml"
  - "**/*.yaml"
  - "{unity-project-dir}/Assets/Scripts/Tools/**/*.cs"
  - "{unity-project-dir}/Assets/Scripts/Editor/**/*.cs"
---

# AI-Facing CLI Tool Design Rules

CLI tools in this project are designed for AI callers (Claude Code / Agents).
AI self-corrects through error messages, not documentation. Silent fallbacks make AI believe its call was correct.

## Required Parameters (CRITICAL)

Business parameters (scene paths, branch names, build targets, etc.) must NOT have default values. Missing parameters must cause an immediate error exit.

```bash
# ✅ Correct — missing argument triggers explicit error with usage hint
if [[ -z "${1:-}" ]]; then
    echo "ERROR: Missing required <scene-path> argument." >&2
    echo "Usage: bash run-test.sh <scene-path> <test-filter>" >&2
    echo "  <scene-path> must be a relative path starting with Assets/, ending with .unity" >&2
    exit 1
fi

# ❌ Wrong — AI forgets the argument, script silently uses a default
local scene="${1:-Assets/Scenes/Main.unity}"
```

Rule of thumb: if AI might pass a different value each call, it is a required parameter.

## Fail-Fast (CRITICAL)

Errors must terminate immediately with a non-zero exit code. Never swallow errors with `|| echo "0"`, `|| true`, or empty catch blocks.

```bash
# ✅ Correct — parse failure is explicitly surfaced
ERROR_COUNT=$(grep -o '"errorCount":[0-9]*' <<< "$JSON" | grep -o '[0-9]*') || {
    echo "WARNING: Failed to parse errorCount from compile output" >&2
    ERROR_COUNT="PARSE_ERROR"
}

# ❌ Wrong — parse failure silently becomes 0
ERROR_COUNT=$(grep -o '"errorCount":[0-9]*' <<< "$JSON" | grep -o '[0-9]*' || echo "0")
```

```csharp
// ✅ Correct — batch mode failure exits immediately
catch (Exception e)
{
    Debug.LogError($"[BatchTool] {e.Message}");
    if (Application.isBatchMode) EditorApplication.Exit(1);
}

// ❌ Wrong — failure is logged but execution continues
catch (Exception e) { Debug.LogError(e.Message); }
```

## Exit Code / Output Consistency

If JSON output contains `"success": false`, the exit code MUST be non-zero. Callers may only check the exit code.

| Exit Code | Meaning                            |
|-----------|------------------------------------|
| 0         | Success                            |
| 1         | Known failure (compile error, test failure, invalid input) |
| 2         | Blocked by policy (hook rejection) |
| 3         | Infrastructure error (Unity not found, timeout) |

## Error Messages Are Documentation

Every error message must include three elements — this is the AI's only source for self-correction:
1. What is missing / what went wrong
2. Correct usage example (full command line)
3. Parameter format requirements

```bash
echo "ERROR: Missing required --scene argument." >&2
echo "Usage: bash unity-test.sh smoke --scene Assets/Scenes/<YourScene>.unity" >&2
echo "  --scene value must be a relative path starting with Assets/, ending with .unity" >&2
exit 1
```

## Self-check Checklist

- [ ] Does every business parameter fail loudly when missing (no silent defaults)?
- [ ] Does every error path exit with a non-zero code?
- [ ] Does `"success": false` in JSON output always pair with a non-zero exit code?
- [ ] Does every error message include what went wrong, correct usage, and format requirements?
