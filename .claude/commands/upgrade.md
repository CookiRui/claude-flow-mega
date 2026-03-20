---
description: Upgrade claude-flow templates to the latest version
argument-hint: [--force]
---

# /upgrade

Upgrades the current project's claude-flow configuration to the latest template version. Detects new files, changed files, and safely merges updates without overwriting user customizations.

## Phase 1: Discover

1. Determine the claude-flow source directory:
   - Check if `node_modules/claude-autosolve/template/` exists (npm install)
   - Check if a `CLAUDE_FLOW_PATH` environment variable is set
   - Ask user for path if neither found

2. List all files in the source `template/` directory.

3. For each template file, classify it:

| Status | Condition | Action |
|--------|-----------|--------|
| **NEW** | File exists in template/ but not in project | Will be added |
| **UNCHANGED** | File exists in both, content is identical | Skip |
| **UPSTREAM_ONLY** | File exists in both, user version matches an older template version | Safe to update |
| **USER_MODIFIED** | File exists in both, user has customized it | Show diff, ask user |
| **USER_ONLY** | File exists in project but not in template | Leave untouched |

4. Output a summary table:
   ```
   /upgrade scan results:

   NEW (will add):
     + .claude/agents/feature-builder.md
     + .claude/hooks/protect-files.sh

   SAFE UPDATE (upstream changes only):
     ↑ .claude/commands/deep-task.md

   CONFLICT (you modified + upstream changed):
     ⚠ .claude/constitution.md — review needed

   UNCHANGED (skip):
     = .claude/skills/tdd/SKILL.md
   ```

5. Ask user to confirm before making any changes. If `--force` argument was passed, skip confirmation for NEW and SAFE UPDATE (still confirm CONFLICT).

## Phase 2: Apply

For each file by status:

- **NEW**: Copy from template to project. Create parent directories if needed.
- **SAFE UPDATE**: Replace with new version. Show brief summary of what changed.
- **CONFLICT**: Show a side-by-side or unified diff. Ask user to choose:
  - (a) Keep mine — skip this file
  - (b) Take upstream — overwrite with template version
  - (c) Merge — manually apply specific sections (AI-assisted)
- **UNCHANGED / USER_ONLY**: Skip.

## Phase 3: Post-upgrade

1. List all changes made.
2. If new commands were added, mention them: "New commands available: /command-name"
3. If new agents were added, mention them: "New agents available: agent-name"
4. If constitution governance rules changed, flag for review.
5. Suggest: `git add .claude/ && git commit -m "chore: upgrade claude-flow templates"`

## Notes

- Never delete user files that don't exist in the template.
- Never overwrite user customizations without explicit confirmation.
- The scripts/ directory is also checked (persistent-solve.py, repo-map.py, lint-feedback.sh).
- If the user has files in .claude/skills/ that are not in the template, they are custom skills and should be left untouched.
