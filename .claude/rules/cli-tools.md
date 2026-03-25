# CLI Tools Rules

> Supplements the constitution with details it can't cover. If derivable from the constitution, delete it.

## Rule 1: Required parameters have no defaults (per Constitution §3)

Business-logic parameters (paths, goal descriptions, target directories) must be explicitly provided. Never silently default to a value that could mask user intent.

```python
# ✅ Correct
parser.add_argument("--target", required=True, help="Target project directory")

# ❌ Wrong
parser.add_argument("--target", default=".")
```

**Exceptions:** Timeouts, log levels, output formats, and infrastructure defaults (e.g., `--timeout 120`) are acceptable.

## Rule 2: Fail-fast with non-zero exit (per Constitution §3)

On error, exit immediately with a non-zero code. Do not continue with partial results or swallow exceptions.

```python
# ✅ Correct
if not os.path.isdir(target):
    print(f"Error: {target} is not a valid directory", file=sys.stderr)
    sys.exit(1)

# ❌ Wrong
if not os.path.isdir(target):
    print("Warning: directory not found, using current dir")
    target = "."
```

**Exceptions:** Batch operations may collect errors and report at the end with a non-zero exit.

## Rule 3: Exit code matches output (per Constitution §3)

If the script outputs structured data (JSON), the exit code must be consistent. `"success": false` in output must accompany `exit 1`.

```python
# ✅ Correct
print(json.dumps({"success": False, "error": "compile failed"}))
sys.exit(1)

# ❌ Wrong
print(json.dumps({"success": False, "error": "compile failed"}))
sys.exit(0)  # misleads the caller
```

**Exceptions:** None.

## Rule 4: Error messages are documentation (per Constitution §3)

Every error message must contain: (1) what failed, (2) a correct usage example, (3) expected parameter format.

```text
# ✅ Correct
Error: --target is required but was not provided.
Usage: python install.py --target /path/to/project
  --target: path to project directory (required)
  --preset: optional preset name (e.g., unity)

# ❌ Wrong
Error: missing required argument
```

**Exceptions:** Internal helper functions called only by other scripts may use shorter messages.

## Self-check Checklist

- [ ] Do all required parameters explicitly require a value (no silent defaults for business logic)?
- [ ] Does the script exit non-zero on every error path?
- [ ] If JSON output includes `"success": false`, does exit code also signal failure?
- [ ] Does every error message include what failed, correct usage, and parameter format?
