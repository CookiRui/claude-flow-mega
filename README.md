# claude-flow

**[English](README_EN.md)**

> 让 Claude Code 拥有结构化项目认知 + 自主执行能力的开源框架。

## 这是什么？

两套互补的系统，让 Claude Code 从"每次对话从零开始"变成"像读完所有内部文档的新员工"：

1. **4 层项目配置** — Constitution → Rules → Skills → Commands，用渐进式披露控制 token 成本（[详细文档](docs/project-config.md)）
2. **8 层自主执行引擎** — 目标审查 → DAG 分解 → 并行执行 → 三级验证 → 元学习（[详细文档](docs/autonomous-engine.md)）

**特点**：
- 一条命令自动分析项目并生成所有配置，无需手动填写
- 3 个专业化 Agent 模板（功能实现、代码审查、对抗测试）
- 4 个实用工具脚本（持久化循环、分层代码地图、模块级规则加载、Lint 反馈闭环）
- 防护 Hooks（文件保护 + compact 后上下文恢复）+ deny 权限模板
- CI/CD 模板（GitHub Actions 构建/测试 + AI 代码审查）
- 代码审查标准模板（REVIEW.md，3 维度 × 3 级别）
- **引擎 Preset 系统**：`--preset unity` 一键叠加 Unity 专属配置（batch mode 脚本、AutoTest 框架、C# 运行时）
- 从 100+ 配置文件的实际项目中提炼的方法论

---

## 快速开始

### 1. 安装到你的项目

```bash
# 方式 A：npx（推荐）
npx claude-autosolve init                              # 安装核心到当前目录
npx claude-autosolve init --preset unity               # 安装核心 + Unity preset
npx claude-autosolve init /path/to/project --force     # 安装到指定目录，强制覆盖

# 方式 B：Python
git clone https://github.com/CookiRui/claude-flow.git
cd claude-flow
python install.py /path/to/your-project                # 核心
python install.py /path/to/your-project --preset unity  # 核心 + Unity
```

已有文件不会被覆盖，加 `--force` 强制覆盖。

**可用 Preset**：`unity`（更多引擎 preset 计划中）

### 2. 让 AI 自动配置

在项目目录下启动 Claude Code，运行：

```
/init-project
```

**已有项目** — AI 会自动：
- 扫描代码库，识别语言、框架、架构模式
- 生成 constitution（AI 不知道就会写错的项目约束）
- 生成 rules（编码规范补充细则）
- 生成 .claudeignore（排除构建产物和依赖）
- 配置 Hooks（lint 自动反馈闭环）
- 按需生成项目特有的 Skills（自定义框架/API 使用指南）

**新项目（空目录）** — AI 会引导你：
- 描述项目的语言、框架、架构
- 自动生成项目脚手架（manifest、目录结构、入口文件）
- 基于你的描述生成所有 claude-flow 配置

**整个过程只需确认一次 AI 的分析结果，不需要手动填任何占位符。**

### 3. 开始使用

```
> 给用户接口加一个按邮箱查询的功能          # 日常开发，AI 自动遵循 constitution
> /feature-plan-creator 用户权限系统         # 复杂功能：需求分析 → 技术方案 → 微任务
> /bug-fix 登录偶尔返回 500                  # 修 Bug：诊断 → 回归测试 → 修复 → 经验固化
> /deep-task 将认证系统从 session 迁移到 JWT  # 复杂任务：DAG 分解 → 并行执行 → 三级验证
```

超出单会话的超大型任务（XL 级）：

```bash
# DAG 模式（默认）：自动分解为子任务，原子化执行，费用追踪
python scripts/persistent-solve.py "重构整个数据层架构"

# 递归 DAG 模式：按复杂度递归拆解 + 看板输出
python scripts/persistent-solve.py "重构整个数据层架构" --recursive

# 控制预算
python scripts/persistent-solve.py "重构整个数据层架构" --max-budget-usd 3.0 --per-task-budget 0.3
```

---

## 内置命令

| 命令 | 用途 |
|------|------|
| `/init-project` | 自动分析项目并生成所有 claude-flow 配置 |
| `/feature-plan-creator <name>` | 需求确认 → 技术方案 → ≤5 分钟微任务拆解 |
| `/bug-fix <description>` | 根因诊断 → 回归测试 → 修复 → 经验固化 |
| `/deep-task <goal>` | 8 层自主引擎：复杂度分流 → DAG 分解 → 并行 Agent → 三级验证 → 元学习 |
| `/upgrade` | 升级 claude-flow 模板到最新版本（检测新增/冲突/安全更新） |

---

## 项目结构

```
template/                              # 核心模板（所有项目都装）
├── CLAUDE.md                          # 根入口：架构速览
├── REVIEW.md                          # 代码审查标准（3 维度 × 3 级别）
├── .claudeignore                      # AI 忽略文件配置
├── .github/workflows/ci.yml           # CI/CD 模板（构建/测试 + AI 代码审查）
└── .claude/
    ├── constitution.md                # 宪法模板（4-7 条核心约束 + 强制执行协议）
    ├── settings.json                  # 预配置 Hooks + deny 权限
    ├── agents/                        # 3 个 Agent（功能实现/代码审查/对抗测试）
    ├── hooks/                         # 文件保护 + compact 上下文恢复
    ├── rules/                         # 编码风格 + Git 工作流 + 安全
    ├── skills/                        # TDD + 验证 + Skill 模板
    └── commands/                      # init-project / deep-task / bug-fix / ...

presets/                               # 引擎专属叠加层
└── unity/                             # Unity preset（--preset unity 安装）
    ├── .claude/
    │   ├── scripts/                   # 8 个 batch mode 脚本（编译/测试/资产操作）
    │   ├── rules/                     # unity-scripts / unity-assets / cli-tools
    │   ├── hooks/                     # validate-bash / validate-meta-staged
    │   ├── agents/                    # unity-dev / git-ops + 更新版 feature-builder/test-writer
    │   └── skills/autotest/           # AutoTest 框架使用指南
    ├── unity-runtime/                 # C# 运行时（26 文件 + 3 asmdef）
    │   ├── Scripts/Gameplay/AutoTest/ # IInputProvider + TestInputProvider + AutoTestBridge
    │   ├── Scripts/Tools/Editor/      # BatchMode + AutoTest Core/Runner/Results + UnityOps
    │   └── Scripts/Tests/Editor/      # SanityTests + asmdef
    ├── .gitea/workflows/              # Gitea CI（编译+测试+AI 审查）
    ├── REVIEW.md                      # 含 Unity 性能规则的增强版
    ├── .gitignore                     # Unity 专用
    └── .gitattributes                 # LFS 模式（贴图/模型/音频）
```

---

## 工具脚本

### persistent-solve.py — 原子化 DAG 调度器

```bash
# DAG 模式（默认）：Claude 分解目标为子任务 DAG → 每个子任务独立 claude -p 调用
python scripts/persistent-solve.py "让游戏帧率稳定 60fps"
python scripts/persistent-solve.py "重构认证系统" --max-budget-usd 3.0 --per-task-budget 0.3

# 递归 DAG 模式：自动按复杂度递归拆解，直到所有叶子任务 ≤5 分钟
python scripts/persistent-solve.py "重构整个数据层架构" --recursive
python scripts/persistent-solve.py "重构整个数据层架构" --recursive --verify-level l2

# Legacy 模式：原始 WIP 握手循环（一轮一个完整会话）
python scripts/persistent-solve.py "修复内存泄漏" --mode legacy

# 通用选项
python scripts/persistent-solve.py "目标" --max-rounds 5 --max-time 3600
```

**DAG 模式**（默认）将目标分解为子任务 DAG，每个子任务作为独立的 `claude -p` 调用执行。支持：
- **费用追踪**：通过 `--output-format json` 获取每个子任务的 token 用量和费用
- **预算控制**：`--max-budget-usd` 总预算 + `--per-task-budget` 单任务预算，到达即熔断
- **并行执行**：无文件冲突的子任务通过 `ThreadPoolExecutor` 进程级并行
- **熔断保护**：预算、时间、轮次、无进展检测四重熔断

**递归 DAG 模式**（`--recursive`）在 DAG 模式基础上增加递归拆解能力：
- **递归拆解**：按复杂度自动收敛（C≤2 停止，C≥3 继续递归），硬上限 5 层深度
- **原子提交**：每个叶子任务产出一个独立 checkpoint commit
- **验证分级**：按复杂度自动选择验证级别（C:1-2 → L1，C:3-4 → L1+L2，C:5 → L1+L2+L3）
- **局部重规划**：失败时只重新拆解失败节点及其下游，不影响已完成的分支
- **看板输出**：实时写 `kanban.json` + 终端树形进度显示

**看板输出**（`kanban.json`）：执行过程中自动生成 `.claude-flow/kanban.json`，包含任务树结构、状态汇总（total/done/failed/pending/running）和费用追踪（total_cost_usd）。终端同步显示树形进度：
```
[running] 重构整个数据层架构  ($2.34)
├─ [done] T1: 数据模型重构  ($0.40)  abc1234
│  ├─ [done] T1.1: 实体定义  ($0.15)  def5678
│  └─ [done] T1.2: 关系映射  ($0.25)  ghi9012
├─ [running] T2: 查询层重写  ($0.80)
└─ [pending] T3: 迁移脚本
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--recursive` | `False` | 启用递归 DAG 拆解（显式 opt-in） |
| `--kanban` | `True` | 启用看板输出（终端树形 + JSON 文件） |
| `--kanban-path PATH` | `.claude-flow/kanban.json` | 看板 JSON 输出路径 |
| `--verify-level` | `auto` | 验证级别覆盖（`auto`\|`l1`\|`l2`\|`l3`，auto = 按复杂度分级） |

**Legacy 模式** 保留原始行为：每轮一个完整 Claude 会话，通过 `.claude-flow/wip.md` 在会话间传递进度。

> **何时用 `/deep-task` vs `persistent-solve.py`**：大多数 L 级任务，`/deep-task` 在单会话内就能完成（并行 Agent + 模型路由）。只有真正超出单会话预算的 XL 级任务才需要 `persistent-solve.py`。

### repo-map.py — 分层代码地图生成器

```bash
# 分层模式（默认）：生成 L0 全局概览 + L1 模块级符号索引
python scripts/repo-map.py /path/to/project
python scripts/repo-map.py /path/to/project --incremental   # 增量更新（基于 git diff）
python scripts/repo-map.py /path/to/project --level L0      # 仅生成 L0
python scripts/repo-map.py /path/to/project --level L1 --module auth  # 仅生成某模块 L1
python scripts/repo-map.py /path/to/project --list-modules   # 列出检测到的模块

# 传统平面模式（向后兼容）
python scripts/repo-map.py /path/to/project --format md      # 输出 .repo-map.md
python scripts/repo-map.py /path/to/project --format json     # 输出 .repo-map.json
```

**分层输出**（`.repo-map/` 目录）：
- **L0**（`L0.md`）— 全局概览：模块表格 + 跨模块依赖 + 关键入口点（<100 行，始终注入上下文）
- **L1**（`modules/{name}.md`）— 模块级符号索引：按文件分组的类/函数/方法（<200 行，按需加载）
- **L2** — 按需展开：直接读取源文件（无需生成）

**增量更新**：`--incremental` 基于 git diff 仅重扫变更文件，与缓存合并，大幅减少重建时间。
**模块自动检测**：从顶级目录自动检测模块，支持 `config.json` 手动配置。

### scope-loader.py — 模块级作用域规则加载器

```bash
python scripts/scope-loader.py                                    # 从 git diff 自动检测
python scripts/scope-loader.py --files "net/client.py,ui/app.py"  # 指定文件
python scripts/scope-loader.py --module networking                 # 指定模块
python scripts/scope-loader.py --format json                      # JSON 输出
python scripts/scope-loader.py --format inject                    # stdout 注入（默认）
```

根据 git diff 影响范围，自动加载相关模块的 constitution 和 rules。支持：
- **模块检测**：与 repo-map.py 共享模块边界（顶级目录 + config.json 配置）
- **继承机制**：模块 constitution 叠加根级约束（不替换），可添加模块特有规则
- **输出格式**：inject（stdout 注入，供 hook 使用）或 JSON（供程序消费）

### lint-feedback.sh — 双向 Lint/Test 反馈闭环

配置为 Claude Code Hook：编辑 → 自动 lint → 失败 → 错误反馈给 AI → AI 自动修复 → 再 lint → 通过。支持 ESLint / Ruff / dotnet format / golangci-lint / Clippy。

---

## Unity Preset

`--preset unity` 在核心模板之上叠加完整的 Unity 自动化测试链路：

```bash
npx claude-autosolve init --preset unity
```

**叠加内容**：

| 类别 | 内容 |
|------|------|
| **Batch Mode 脚本** | 编译、EditMode 测试、PlayMode/AutoTest、资产操作、编译日志解析 |
| **C# 运行时** | AutoTest 框架（TestCase/TestAction/TestCondition/TypeRegistry）+ IInputProvider 确定性输入注入 + BatchPlayModeRunner + UnityOps |
| **Unity Rules** | C# 命名规范、.meta 文件安全、热路径零分配、CompareTag、组件缓存 |
| **Unity Hooks** | validate-bash（拦截 rm Library 等）、validate-meta-staged（.meta 提交完整性） |
| **Unity Agents** | unity-dev（C# 开发）、git-ops（Git+LFS+.meta） |
| **AutoTest Skill** | IInputProvider 模式、JSON 测试用例格式、三阶段执行生命周期 |
| **CI/CD** | Gitea Actions（编译检查 + EditMode 测试 + Claude Code PR 审查） |
| **REVIEW.md** | 新增 PERF-U1~U10 移动端性能规则 + Unity/C# 技术检查清单 |

**自动化测试完整链路**：

```
unity-editmode-test.sh  → Unity TestRunner (NUnit)  → XML → JSON
unity-game-test.sh      → BatchPlayModeRunner → AutoTest 框架 → result.json
unity-compile.sh        → Unity batch mode 编译    → compile.log → JSON
unity-ops.sh            → UnityOpsRunner → 场景/预制体/材质操作 → result.json
```

所有脚本使用 `{placeholder}` 模板化，`/init-project` 自动检测 Unity 项目并填充具体值。

---

## 文档

| 文档                                                  | 内容                                       |
|-------------------------------------------------------|--------------------------------------------|
| [4 层项目配置方法论](docs/project-config.md)           | Constitution/Rules/Skills/Commands 完整指南 |
| [8 层自主执行引擎](docs/autonomous-engine.md)          | 设计原理 + 实操路径 + 场景速查 + 踩坑记录 |
| [持久化循环](docs/persistent-loop.md)                  | 跨会话 WIP 机制 + 持久化循环调度器          |

---

## 与其他方案的对比

| 特性             | claude-flow                            | 原生 Claude Code              | Superpower-style 方案        |
|------------------|----------------------------------------|-------------------------------|------------------------------|
| 项目认知结构     | 4 层分级（Constitution→Commands）      | 平面 CLAUDE.md                | 宪法 + Rules（无 Skills 层） |
| Agent 协作       | 3 专业 Agent（功能实现 / 代码审查 / 对抗测试）| 无内置模板              | 无                           |
| Hooks 防护       | 文件保护 + Lint 反馈 + compact 上下文恢复 | 单向 Hooks                 | 无                           |
| 代码审查标准     | REVIEW.md 模板（3 维度 × 3 级别）      | 无                            | 无                           |
| CI/CD 模板       | GitHub Actions（构建/测试 + AI 审查）  | 无                            | 无                           |
| 费用预算控制     | `--max-budget-usd` 实际费用追踪 + 熔断 | 无                            | 无                           |
| 自主执行引擎     | 8 层 `/deep-task`（DAG→并行Agent→验证→元学习）| 无                       | 无                           |
| 一键初始化       | `/init-project` 自动分析生成           | 无                            | 手动配置                     |
| 跨会话持久化     | 递归 DAG 调度 + 看板输出 + WIP + 费用追踪 | 无                            | 无                           |
| 验证体系         | 三级 + 多 Agent 对抗循环（Reviewer↔Executor 收敛）| 无                     | 无                           |
| 内置 TDD 强制    | ✅ 通过宪法强制执行                     | ❌                            | ❌                           |

---

## 适用场景

- **中大型项目**：多模块、多人协作、有明确架构约束
- **长期维护项目**：需要 AI 持续理解项目演进
- **质量敏感项目**：需要 TDD、验证清单、回归测试保障
- **复杂任务**：跨模块重构、性能优化、新子系统开发

- **新项目**：从空目录开始，AI 引导式搭建脚手架 + 配置

**不适用**：一次性脚本、快速原型、探索性实验（直接用原生 Claude Code 更高效）。

---

## License

MIT
