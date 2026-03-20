# Security Rules

> Supplements the constitution with details it can't cover. If derivable from the constitution, delete it.

## Rule 1: No secrets in code (per Constitution §3)

Never hardcode API keys, passwords, tokens, or any credentials directly in source code. This applies to both `scripts/` and `template/` files.

```python
# ✅ Correct
api_key = os.environ.get("ANTHROPIC_API_KEY")

# ❌ Wrong
api_key = "sk-ant-abc123hardcodedtoken"
```

**Exceptions:** Non-sensitive public configuration values (GitHub repo URLs, npm package names) may be inlined.

## Rule 2: Input validation in scripts (per Constitution §3)

All Python scripts in `scripts/` accept external input (CLI args, file paths, Claude API responses). Validate before processing.

```python
# ✅ Correct
if not os.path.isdir(target_dir):
    print(f"Error: {target_dir} is not a valid directory", file=sys.stderr)
    sys.exit(1)

# ❌ Wrong — passing raw user input to shell
subprocess.run(f"claude -p '{user_goal}'", shell=True)
```

**Exceptions:** Internal function calls within a script may trust their callers.

## Self-check Checklist

- [ ] Are there any hardcoded secrets, tokens, or passwords in the changed files?
- [ ] Do CLI scripts validate user-provided paths and arguments before use?
- [ ] Are subprocess calls using list form (not shell=True with string interpolation)?
