# {project-name}

<!-- Usage: replace all {placeholders}, remove unnecessary subsystems, then delete this comment -->

## Architecture Overview

```
{subsystem-a}/  -> {one-line responsibility}
{subsystem-b}/  -> {one-line responsibility}
{shared-layer}/ -> {protocols/configs/shared libs}
Docs/           -> Design documents
```

<!-- Example (game project):
```
Client/     -> Unity client (C#)
Server/     -> Go game server
Proto/      -> Protobuf protocol definitions
Configs/    -> Configuration tables
Docs/       -> Design documents
```
-->

## Work Conventions

- Code comments in {language}, variable/function names in English
- {project-specific constraint 1, e.g.: game logic only in hot-update layer}
- {project-specific constraint 2, e.g.: async must use UniTask, no coroutines}

<!-- Remove rules that Claude already follows by default ("read before editing", "ask if unsure"). Keep only project-specific rules. -->

## Subsystems

@{subsystem-a}/CLAUDE.md
@{subsystem-b}/CLAUDE.md
