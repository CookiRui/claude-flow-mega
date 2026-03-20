# Git Workflow Rules

> Supplements the constitution with details it can't cover. If derivable from the constitution, delete it.

## Rule 1: Commit message format (per Constitution §4)

All commit messages must follow the `type(scope): description` convention. Description may be in Chinese or English. Allowed types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`, `perf`.

```text
// ✅ Correct
feat: 动态模型路由 + learnings 按域分文件淘汰机制
fix: /init-project 补齐新模板文件的生成逻辑
docs: 记录引擎升级任务的执行经验
checkpoint: T2 init-project generates learnings/ directory

// ❌ Wrong
fixed stuff
WIP
update
```

**Exceptions:** Checkpoint commits during `/deep-task` execution use `checkpoint: {task-id} {description}` format.

## Rule 2: Single master branch (per Constitution §4)

All work happens directly on `master`. No feature branches — this project is single-developer with atomic commits.

```text
// ✅ Correct
git push origin master

// ❌ Wrong
git checkout -b feat/some-feature
```

**Exceptions:** The `feature-builder` agent uses worktrees for isolation, which is acceptable.

## Rule 3: Atomic commits (per Constitution §4)

Each commit must serve a single, well-defined purpose. Do not bundle unrelated changes into one commit.

```text
// ✅ Correct
— One commit adds a new command
— One commit fixes a bug in an existing command
— One commit updates docs to match

// ❌ Wrong
— One commit that adds a command, fixes two bugs, and updates README
```

**Exceptions:** When template/ and .claude/ must stay in sync, bundling both in one commit is preferred over splitting.

## Self-check Checklist

- [ ] Does every commit message follow `type(scope): description` with an allowed type?
- [ ] Does each commit contain only one logical change?
- [ ] Was `git push origin master` run after committing?
