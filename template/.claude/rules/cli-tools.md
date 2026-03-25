# CLI Tools Rules

> Supplements the constitution with details it can't cover. If derivable from the constitution, delete it.

## Rule 1: Required parameters have no defaults (per Constitution §{N})

Business-logic parameters (paths, branch names, review types, feature names) must be explicitly provided. Never silently default to a value that could mask user intent.

```{language}
// ✅ Correct
parser.add_argument("--scene", required=True, help="Path to the scene file")

// ❌ Wrong
parser.add_argument("--scene", default="Assets/Scenes/Main.unity")
```

**Exceptions:** Timeouts, log levels, output formats, and infrastructure defaults (e.g., `--timeout 120`) are acceptable.

## Rule 2: Fail-fast with non-zero exit (per Constitution §{N})

On error, exit immediately with a non-zero code. Do not continue with partial results or swallow exceptions.

```{language}
// ✅ Correct
if not os.path.isdir(target):
    print(f"Error: {target} is not a valid directory", file=sys.stderr)
    sys.exit(1)

// ❌ Wrong
if not os.path.isdir(target):
    print("Warning: directory not found, using current dir")
    target = "."
```

**Exceptions:** {exception-scenarios — e.g., batch operations may collect errors and report at the end with a non-zero exit}

## Rule 3: Exit code matches output (per Constitution §{N})

If the script outputs structured data (JSON), the exit code must be consistent. `"success": false` in output must accompany `exit 1`. Never return exit 0 with an error payload.

```{language}
// ✅ Correct
print(json.dumps({"success": False, "error": "compile failed"}))
sys.exit(1)

// ❌ Wrong
print(json.dumps({"success": False, "error": "compile failed"}))
sys.exit(0)  # misleads the caller
```

**Exceptions:** None. This rule has no exceptions.

## Rule 4: Error messages are documentation (per Constitution §{N})

Every error message must contain three parts: (1) what failed, (2) a correct usage example, (3) expected parameter format. The AI agent reading this error should be able to self-correct without external help.

```text
// ✅ Correct
Error: --scene is required but was not provided.
Usage: python run-test.py --scene Assets/Scenes/Main.unity --filter "TestClass"
  --scene: path to .unity scene file (required)
  --filter: test name filter (optional, default: run all)

// ❌ Wrong
Error: missing required argument
```

**Exceptions:** {exception-scenarios — e.g., internal helper functions called only by other scripts may use shorter messages}

## Self-check Checklist

- [ ] Do all required parameters explicitly require a value (no silent defaults for business logic)?
- [ ] Does the script exit non-zero on every error path?
- [ ] If JSON output includes `"success": false`, does exit code also signal failure?
- [ ] Does every error message include what failed, correct usage, and parameter format?
