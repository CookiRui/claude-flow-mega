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

### 1. 复制框架到你的项目

```bash
cp -r template/ your-project/
cp -r scripts/ your-project/scripts/
```

### 2. 让 AI 自动配置

在项目目录下启动 Claude Code，运行：

```
/init-project
```

AI 会自动：
- 扫描代码库，识别语言、框架、架构模式
- 生成 constitution（AI 不知道就会写错的项目约束）
- 生成 rules（编码规范补充细则）
- 生成 .claudeignore（排除构建产物和依赖）
- 配置 Hooks（lint 自动反馈闭环）
- 按需生成项目特有的 Skills（自定义框架/API 使用指南）

**整个过程只需确认一次 AI 的分析结果，不需要手动填任何占位符。**

### 3. 开始使用

```
> 给用户接口加一个按邮箱查询的功能          # 日常开发，AI 自动遵循 constitution
> /feature-plan-creator 用户权限系统         # 复杂功能：需求分析 → 技术方案 → 微任务
> /bug-fix 登录偶尔返回 500                  # 修 Bug：诊断 → 回归测试 → 修复 → 经验固化
```

跨会话的大型任务：

```bash
python scripts/persistent-solve.py "将认证系统从 session 迁移到 JWT"
```

---

## 内置命令

| 命令 | 用途 |
|------|------|
| `/init-project` | 自动分析项目并生成所有 claude-flow 配置 |
| `/feature-plan-creator <name>` | 需求确认 → 技术方案 → ≤5 分钟微任务拆解 |
| `/bug-fix <description>` | 根因诊断 → 回归测试 → 修复 → 经验固化 |

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
        └── bug-fix.md                 # Bug 诊断 → 修复 → 经验固化
```

---

## 工具脚本

### persistent-solve.py — 跨会话持久化循环

```bash
python scripts/persistent-solve.py "让游戏帧率稳定 60fps"
python scripts/persistent-solve.py "重构认证系统" --max-rounds 5 --max-time 1800
```

自动在 Claude Code 会话间循环：执行 → 保存 WIP → 恢复 → 继续，直到目标达成或触发熔断。

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
| Token 预算控制   | 渐进式披露 + 预算指南                  | 无                            | 无                           |
| 自主执行引擎     | 8 层（目标审查→元学习）                | 无                            | 无                           |
| 一键初始化       | `/init-project` 自动分析生成           | 无                            | 手动配置                     |
| Lint 反馈闭环    | 双向（编辑→lint→自动修→再lint）        | 单向 Hooks                    | 无                           |
| 跨会话持久化     | 持久化循环 + WIP                       | 无                            | 无                           |
| 验证体系         | 三级（L1自检/L2对抗/L3端到端）         | 无                            | 无                           |
| 内置 TDD 强制    | ✅ 通过宪法强制执行                     | ❌                            | ❌                           |

---

## 适用场景

- **中大型项目**：多模块、多人协作、有明确架构约束
- **长期维护项目**：需要 AI 持续理解项目演进
- **质量敏感项目**：需要 TDD、验证清单、回归测试保障
- **复杂任务**：跨模块重构、性能优化、新子系统开发

**不适用**：一次性脚本、快速原型、探索性实验（直接用原生 Claude Code 更高效）。

---

## License

MIT
