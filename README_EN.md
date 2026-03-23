# claude-flow

> Give Claude Code structured project cognition + autonomous execution capabilities.

**[中文文档](README.md)**

## What is this?

Two complementary systems that transform Claude Code from "starting from scratch every conversation" into "a new hire who's read all the internal docs":

1. **4-Layer Project Config** — Constitution → Rules → Skills → Commands, with progressive disclosure to control token costs ([docs](docs/project-config.md))
2. **8-Layer Autonomous Engine** — Goal review → DAG decomposition → Parallel execution → 3-level verification → Meta-learning ([docs](docs/autonomous-engine.md))

**Highlights**:
- One command auto-analyzes your project and generates all configuration — zero manual editing
- 3 specialized Agent templates (feature builder, code reviewer, adversarial test writer)
- 3 utility scripts (atomic DAG scheduler, code map, lint feedback loop)
- Protective Hooks (file protection + post-compact context recovery) + deny permission templates
- CI/CD template (GitHub Actions build/test + AI code review)
- Code review standards template (REVIEW.md, 3 dimensions × 3 severity levels)
- **Engine Preset System**: `--preset unity` overlays full Unity automation (batch mode scripts, AutoTest framework, C# runtime)
- Methodology distilled from real projects with 100+ config files

---

## Quick Start

### 1. Install to your project

```bash
# Option A: npx (recommended)
npx claude-autosolve init                              # Install core to current directory
npx claude-autosolve init --preset unity               # Install core + Unity preset
npx claude-autosolve init /path/to/project --force     # Install to specific directory, force overwrite

# Option B: Python
git clone https://github.com/CookiRui/claude-flow.git
cd claude-flow
python install.py /path/to/your-project                # Core only
python install.py /path/to/your-project --preset unity  # Core + Unity
```

Existing files won't be overwritten unless you pass `--force`.

**Available Presets**: `unity` (more engine presets planned)

### 2. Let AI auto-configure

Launch Claude Code in your project directory and run:

```
/init-project
```

**Existing projects** — AI will automatically:
- Scan the codebase, identify languages, frameworks, architecture patterns
- Generate constitution (project constraints AI would otherwise violate)
- Generate rules (coding style supplements)
- Generate .claudeignore (exclude build artifacts and dependencies)
- Configure Hooks (lint auto-feedback loop)
- Generate project-specific Skills as needed (custom framework/API guides)

**New projects (empty directory)** — AI will guide you through:
- Describing the language, framework, and architecture
- Auto-generating project scaffolding (manifest, directory structure, entry files)
- Generating all claude-flow configs based on your description

**The entire process requires only one confirmation of AI's analysis — no manual placeholder filling.**

### 3. Start using

```
> Add an email-based query to the user API        # Daily dev — AI follows constitution
> /feature-plan-creator user permission system     # Complex feature: requirements → design → micro-tasks
> /bug-fix login occasionally returns 500          # Bug fix: diagnosis → regression test → fix → learning
> /deep-task migrate auth from session to JWT      # Complex task: DAG → parallel execution → 3-level verification
```

For XL tasks that exceed a single session:

```bash
# DAG mode (default): auto-decompose into sub-tasks, atomic execution, cost tracking
python scripts/persistent-solve.py "Refactor the entire data layer"

# Budget control
python scripts/persistent-solve.py "Refactor the entire data layer" --max-budget-usd 3.0 --per-task-budget 0.3
```

---

## Built-in Commands

| Command | Purpose |
|---------|---------|
| `/init-project` | Auto-analyze project and generate all claude-flow configs |
| `/feature-plan-creator <name>` | Requirements → Design → Micro-task breakdown (each ≤5 min) |
| `/bug-fix <description>` | Root cause diagnosis → Regression test → Fix → Learning capture |
| `/deep-task <goal>` | 8-layer engine: Complexity routing → DAG → Parallel Agents → 3-level verification → Meta-learning |
| `/upgrade` | Upgrade claude-flow templates to latest version (detect new/conflict/safe updates) |

---

## Project Structure

```
template/                              # Core template (installed for all projects)
├── CLAUDE.md                          # Root entry: architecture overview
├── REVIEW.md                          # Code review standards (3 dimensions × 3 levels)
├── .claudeignore                      # AI ignore config
├── .github/workflows/ci.yml           # CI/CD template (build/test + AI review)
└── .claude/
    ├── constitution.md                # Constitution template (4-7 constraints + enforcement)
    ├── settings.json                  # Pre-configured Hooks + deny permissions
    ├── agents/                        # 3 Agents (feature builder / code reviewer / test writer)
    ├── hooks/                         # File protection + post-compact context recovery
    ├── rules/                         # Coding style + Git workflow + Security
    ├── skills/                        # TDD + Verification + Skill template
    └── commands/                      # init-project / deep-task / bug-fix / ...

presets/                               # Engine-specific overlay layers
└── unity/                             # Unity preset (installed with --preset unity)
    ├── .claude/
    │   ├── scripts/                   # 8 batch mode scripts (compile/test/asset ops)
    │   ├── rules/                     # unity-scripts / unity-assets / cli-tools
    │   ├── hooks/                     # validate-bash / validate-meta-staged
    │   ├── agents/                    # unity-dev / git-ops + updated feature-builder/test-writer
    │   └── skills/autotest/           # AutoTest framework usage guide
    ├── unity-runtime/                 # C# runtime (26 files + 3 asmdefs)
    │   ├── Scripts/Gameplay/AutoTest/ # IInputProvider + TestInputProvider + AutoTestBridge
    │   ├── Scripts/Tools/Editor/      # BatchMode + AutoTest Core/Runner/Results + UnityOps
    │   └── Scripts/Tests/Editor/      # SanityTests + asmdef
    ├── .gitea/workflows/              # Gitea CI (compile + test + AI review)
    ├── REVIEW.md                      # Enhanced with Unity performance rules
    ├── .gitignore                     # Unity-specific
    └── .gitattributes                 # LFS patterns (textures/models/audio)
```

---

## Utility Scripts

### persistent-solve.py — Atomic DAG Scheduler

```bash
# DAG mode (default): Claude decomposes goal into sub-task DAG → each sub-task is an independent claude -p call
python scripts/persistent-solve.py "Stabilize game frame rate at 60fps"
python scripts/persistent-solve.py "Refactor auth system" --max-budget-usd 3.0 --per-task-budget 0.3

# Legacy mode: original WIP handshake loop (one full session per round)
python scripts/persistent-solve.py "Fix memory leak" --mode legacy

# Common options
python scripts/persistent-solve.py "Goal" --max-rounds 5 --max-time 3600
```

**DAG mode** (default) decomposes the goal into a sub-task DAG, executing each as an independent `claude -p` call:
- **Cost tracking**: Captures token usage and cost per sub-task via `--output-format json`
- **Budget control**: `--max-budget-usd` total budget + `--per-task-budget` per-task limit — circuit-breaks on reach
- **Parallel execution**: Non-conflicting sub-tasks run in parallel via `ThreadPoolExecutor`
- **Circuit breakers**: Budget, time, rounds, and no-progress detection — 4 layers of protection

**Legacy mode** preserves original behavior: one full Claude session per round, WIP handshake via `.claude-flow/wip.md`.

> **When to use `/deep-task` vs `persistent-solve.py`**: Most L-level tasks can be completed by `/deep-task` within a single session (parallel Agents + model routing). Only truly XL tasks that exceed single-session budgets need `persistent-solve.py`.

### repo-map.py — Code Map Generator

```bash
python scripts/repo-map.py /path/to/project              # Output .repo-map.json
python scripts/repo-map.py /path/to/project --format md   # Output .repo-map.md
python scripts/repo-map.py /path/to/project --no-refs     # Skip reference counting for large codebases
```

Extracts class/function/method definitions, ranks by reference count. Run before large tasks to reduce search tokens by 50-70%.

### lint-feedback.sh — Bidirectional Lint/Test Feedback Loop

Configured as Claude Code Hook: Edit → Auto-lint → Failure → Error feedback to AI → AI auto-fixes → Re-lint → Pass. Supports ESLint / Ruff / dotnet format / golangci-lint / Clippy.

---

## Unity Preset

`--preset unity` overlays a complete Unity automated testing pipeline on top of the core:

```bash
npx claude-autosolve init --preset unity
```

| Category | Contents |
|----------|----------|
| **Batch Mode Scripts** | Compile, EditMode tests, PlayMode/AutoTest, asset operations, log parsing |
| **C# Runtime** | AutoTest framework (TestCase/TestAction/TestCondition/TypeRegistry) + IInputProvider deterministic input injection + BatchPlayModeRunner + UnityOps |
| **Unity Rules** | C# naming, .meta safety, zero hot-path allocations, CompareTag, component caching |
| **Unity Hooks** | validate-bash (block rm Library etc.), validate-meta-staged (.meta commit integrity) |
| **Unity Agents** | unity-dev (C# development), git-ops (Git+LFS+.meta) |
| **AutoTest Skill** | IInputProvider pattern, JSON test case format, 3-phase execution lifecycle |
| **CI/CD** | Gitea Actions (compile check + EditMode tests + Claude Code PR review) |
| **REVIEW.md** | PERF-U1~U10 mobile performance rules + Unity/C# tech checklist |

All scripts use `{placeholder}` templating — `/init-project` auto-detects Unity projects and fills in values.

---

## Comparison

| Feature | claude-flow | Vanilla Claude Code | Superpower-style |
|---------|-------------|---------------------|------------------|
| Project cognition | 4-layer (Constitution→Commands) | Flat CLAUDE.md | Constitution + Rules (no Skills) |
| Agent collaboration | 3 specialized Agents (feature builder / code reviewer / test writer) | No built-in templates | None |
| Protective hooks | File protection + lint feedback + post-compact context recovery | One-way Hooks | None |
| Code review standards | REVIEW.md template (3 dimensions × 3 levels) | None | None |
| CI/CD template | GitHub Actions (build/test + AI review) | None | None |
| Budget control | `--max-budget-usd` real cost tracking + circuit-break | None | None |
| Autonomous engine | 8-layer `/deep-task` (DAG→Parallel Agents→Verification→Meta-learning) | None | None |
| One-click init | `/init-project` auto-analysis | None | Manual config |
| Cross-session persistence | Atomic DAG scheduling + WIP + cost tracking | None | None |
| Verification | 3-level + multi-Agent adversarial loop (Reviewer↔Executor convergence) | None | None |
| Built-in TDD | Enforced via constitution | No | No |

---

## Use Cases

- **Medium-to-large projects**: Multi-module, team collaboration, explicit architecture constraints
- **Long-term maintenance**: AI needs to understand project evolution over time
- **Quality-sensitive projects**: TDD, verification checklists, regression test guarantees
- **Complex tasks**: Cross-module refactoring, performance optimization, new subsystem development
- **New projects**: Start from empty directory — AI-guided scaffolding + configuration

**Not suitable for**: One-off scripts, quick prototypes, exploratory experiments (vanilla Claude Code is more efficient).

---

## License

MIT
