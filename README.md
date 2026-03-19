# claude-flow

> 让 Claude Code 拥有结构化项目认知 + 自主执行能力的开源框架。

## 这是什么？

两套互补的系统，让 Claude Code 从"每次对话从零开始"变成"像读完所有内部文档的新员工"：

1. **4 层项目配置** — Constitution → Rules → Skills → Commands，用渐进式披露控制 token 成本（[详细文档](docs/project-config.md)）
2. **8 层自主执行引擎** — 目标审查 → DAG 分解 → 并行执行 → 三级验证 → 元学习（[详细文档](docs/autonomous-engine.md)）

**特点**：
- 一条命令自动分析项目并生成所有配置，无需手动填写
- 3 个实用工具脚本（持久化循环、代码地图、Lint 反馈闭环）
- 从 100+ 配置文件的实际项目中提炼的方法论

---

## 快速开始

### 1. 安装到你的项目

```bash
# 克隆仓库
git clone https://github.com/CookiRui/claude-flow.git
cd claude-flow

# 一键安装到目标项目
python install.py /path/to/your-project
```

已有文件不会被覆盖，加 `--force` 强制覆盖。

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

---

## 模板结构

```
template/
├── CLAUDE.md                          # 根入口：架构速览
├── .claudeignore                      # AI 忽略文件配置
└── .claude/
    ├── constitution.md                # 宪法模板（4-7 条核心约束 + 强制执行协议）
    ├── settings.json                  # 预配置 Hooks（lint 反馈闭环）
    ├── rules/
    │   └── coding-style.md            # 编码风格规则模板
    ├── skills/
    │   ├── _template/                 # Skill 模板
    │   ├── tdd/SKILL.md               # 内置：TDD 测试驱动开发（强制执行）
    │   └── verification/SKILL.md      # 内置：完成前验证清单（强制执行）
    └── commands/
        ├── init-project.md            # AI 自动分析项目并生成配置
        ├── feature-plan-creator.md    # 需求分析 → 技术方案 → 微任务拆解
        ├── bug-fix.md                 # Bug 诊断 → 修复 → 经验固化
        └── deep-task.md              # 8 层自主执行引擎（DAG + 并行 Agent + 三级验证）
```

---

## 工具脚本

### persistent-solve.py — 原子化 DAG 调度器

```bash
# DAG 模式（默认）：Claude 分解目标为子任务 DAG → 每个子任务独立 claude -p 调用
python scripts/persistent-solve.py "让游戏帧率稳定 60fps"
python scripts/persistent-solve.py "重构认证系统" --max-budget-usd 3.0 --per-task-budget 0.3

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

**Legacy 模式** 保留原始行为：每轮一个完整 Claude 会话，通过 `.claude-flow/wip.md` 在会话间传递进度。

> **何时用 `/deep-task` vs `persistent-solve.py`**：大多数 L 级任务，`/deep-task` 在单会话内就能完成（并行 Agent + 模型路由）。只有真正超出单会话预算的 XL 级任务才需要 `persistent-solve.py`。

### repo-map.py — 代码地图生成器

```bash
python scripts/repo-map.py /path/to/project              # 输出 .repo-map.json
python scripts/repo-map.py /path/to/project --format md   # 输出 .repo-map.md
python scripts/repo-map.py /path/to/project --no-refs     # 大项目跳过引用计数
```

提取类/函数/方法定义，排序引用关系。在大型任务前生成，减少 50-70% 搜索 token。

### lint-feedback.sh — 双向 Lint/Test 反馈闭环

配置为 Claude Code Hook：编辑 → 自动 lint → 失败 → 错误反馈给 AI → AI 自动修复 → 再 lint → 通过。支持 ESLint / Ruff / dotnet format / golangci-lint / Clippy。

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
| 费用预算控制     | `--max-budget-usd` 实际费用追踪 + 熔断 | 无                            | 无                           |
| 自主执行引擎     | 8 层 `/deep-task`（DAG→并行Agent→验证→元学习）| 无                       | 无                           |
| 一键初始化       | `/init-project` 自动分析生成           | 无                            | 手动配置                     |
| Lint 反馈闭环    | 双向（编辑→lint→自动修→再lint）        | 单向 Hooks                    | 无                           |
| 跨会话持久化     | 原子化 DAG 调度 + WIP + 费用追踪       | 无                            | 无                           |
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
