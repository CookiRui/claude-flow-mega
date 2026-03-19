# 8 层自主执行引擎

> **快速使用**：在 Claude Code 中运行 `/deep-task <目标>` 即可启动此引擎。命令会自动完成复杂度分流、DAG 分解、并行 Agent 执行、三级验证和元学习。以下文档是设计原理和方法论参考。

核心是一个 **目标驱动的闭环**，由 8 层组成。但不是每个任务都需要走满 8 层——入口处先做复杂度分流。

## 入口：复杂度分级快速路径

80% 的日常任务不需要完整 8 层流程。入口处用轻量分类器决定走哪条路径。

| 级别                | 判定条件                   | 走哪些层                         | 推荐模型         | 例子                     |
|---------------------|----------------------------|----------------------------------|------------------|--------------------------|
| **S（trivial）**    | 单文件、无依赖、可自动验证 | 直接执行 + L1 验证               | Haiku（快+便宜） | 重命名、格式修复、改注释 |
| **M（standard）**   | 2-5 文件、有明确验证条件   | 目标层 + 执行层 + 安全网 + L1/L2 | Sonnet（平衡）   | 增加 API、修 bug、加功能 |
| **L（complex）**    | 跨模块、涉及架构决策       | 全 8 层                          | Opus（强推理）   | 新子系统、性能优化       |
| **XL（strategic）** | 需要产品/战略层面判断      | 8 层 + 外部决策                  | Opus（强推理）   | 技术选型、架构重构       |

### 判定速查

| 问自己的问题                  | 是   | 否     |
|-------------------------------|------|--------|
| 只改 1 个文件？               | → S  | 继续 ↓ |
| 改 2-5 个文件，验证条件明确？ | → M  | 继续 ↓ |
| 跨模块？涉及架构决策？        | → L  | 继续 ↓ |
| 需要产品/战略层面判断？       | → XL | 回到 L |

```python
def classify_complexity(goal: str) -> str:
    """Entry classifier: determine which path a task should take."""
    signals = analyze_goal(goal)

    if signals.single_file and signals.no_dependencies and signals.auto_verifiable:
        return "S"  # Direct execution, skip review/decomposition/meta-learning
    elif signals.files <= 5 and signals.clear_acceptance_criteria:
        return "M"  # Skip goal review, simplified decomposition, L1/L2 verification
    elif signals.cross_module or signals.architecture_decision:
        return "L"  # Full 8 layers
    else:
        return "XL" # 8 layers + external decision making
```

---

## 各级别执行路径

### S 级：快速路径

执行 → L1 验证 → git commit。不走审查、不走分解、不走元学习。

```
1. 直接用 Edit/Write 工具修改代码
2. 自检：改动是否符合预期
3. git commit -m "checkpoint: {简要描述}"
```

如果执行过程中发现复杂度比预估高 → **立即升级到 M 或 L**。

### M 级：标准路径

简化分解 → 逐个执行 + 检查点 → L1/L2 验证。

```
1. 快速分解为 2-5 个子任务（不需要 DAG，线性即可）
2. 为每个子任务定义完成条件
3. 逐个执行：
   a. 执行子任务
   b. git commit（检查点）
   c. L1 验证（自检）
4. 全部完成后 L2 验证（关键路径才需要）
```

### L/XL 级：完整路径

走完整 8 层流程。这是框架的核心价值所在。

**Step -1**: 生成代码地图 + 选模型

```bash
python scripts/repo-map.py /path/to/project
```

主 Agent 用 **Opus**，子 Agent 按类型选：编辑类 → `Agent(model="haiku")`，搜索/分析 → `Agent(model="sonnet")`，对抗验证 → `Agent(model="sonnet")`

**Step 0**: 目标审查 → **Step 1**: DAG 分解 + 预检 → **Step 2**: 并行执行 → **Step 3**: 三级验证 → **Step 4**: 元学习

---

## 0. 目标审查层 — 先质疑目标本身（L/XL 级）

在投入任何资源之前，先判断目标是否合理。

```python
def autonomous_solve(goal: str, budget: Budget):
    feasibility = assess_feasibility(goal)

    if feasibility.impossible:
        return suggest_goal_revision(goal, feasibility.reason)

    if feasibility.ambiguous:
        clarified_goal = escalate(level=2, ask_clarification=feasibility.questions)
        goal = clarified_goal

    if feasibility.partial:
        tradeoffs = escalate(level=1, notify_tradeoffs=feasibility.tradeoffs)
```

**预判维度**：物理可行性、清晰度、隐含 tradeoff、范围合理性。

## 1. 目标层 — 把模糊目标变成可验证的子任务 DAG

```
用户输入: "让游戏帧率稳定 60fps"
    ↓ 分解为 DAG（有向无环图），标注依赖关系
子目标 1: 定位性能瓶颈（验证条件: 输出 profiler 报告）
子目标 2: 针对 top3 瓶颈各出方案（验证条件: 每个方案有预期收益）  ← 依赖 1
子目标 3a: 实施方案 A + 回归测试  ← 依赖 2
子目标 3b: 实施方案 B + 回归测试  ← 依赖 2（可与 3a 并行）
子目标 4: 达标确认（验证条件: 连续 5 分钟 > 58fps） ← 依赖 3a/3b
```

**关键设计**：
- 每个子目标必须带 **机器可判定的完成条件**
- 子任务之间是 DAG 而非线性列表，无依赖的任务 **并行执行**
- **动态重规划**：每完成一批任务后，根据结果重新评估剩余任务

### 分解预检

```
□ 覆盖性: 所有子任务完成后，原始目标一定达成吗？
□ 独立性: 子任务之间的边界清晰吗？
□ 可验证性: 每个验证条件是否能用工具自动判定？
□ 粒度合理: 太粗还是太细？
□ 依赖正确: DAG 依赖关系正确吗？
```

## 2. 执行层 — Try → Evaluate → Adjust 循环

```
while not 目标达成 and 未超时 and 预算充足:
    1. 规划: 基于当前状态 + 长期记忆 + 元策略 + 残值，选择下一步
    2. 执行: 调用工具（搜索/编码/测试/部署）
    3. 观察: 收集执行结果
    4. 评估: 结果是否推进了目标？
       ├─ 是 → 保存检查点，回归验证，继续
       ├─ 部分 → 调整方案，重试（换策略，不重复）
       └─ 否 → 回溯，萃取残值，尝试替代路径
    5. 学习: 记录"什么有效/什么无效"到工作记忆
```

**防死循环**：同一策略最多 2-3 次 → 失败后必须换方法 → 连续 K 次无进展 → 分级升级。

### 并行冲突检测

```python
ready = task_dag.get_ready_tasks()
groups = detect_conflicts(ready)

for group in groups:
    if len(group) == 1:
        execute(group[0])                    # No conflict
    elif can_isolate(group):
        parallel_execute_isolated(group)     # Each in worktree
    else:
        sequential_execute(group)            # Fall back to sequential
```

### 失败残值萃取

```python
if not result.success:
    rollback(checkpoint)
    salvage = extract_salvage(result)
    # salvage: eliminated hypotheses, reusable code, narrowed scope, intermediate data
```

## 3. 知识层 — 自动学习 + 代码地图

### 代码地图（Repo Map）

在 L/XL 任务开始前，自动扫描代码库生成符号地图。减少 50-70% 搜索 token。

```bash
python scripts/repo-map.py /path/to/project          # 默认含引用计数
python scripts/repo-map.py /path/to/project --no-refs # 大项目跳过引用计数（更快）
```

### 知识获取的 3 种模式

| 模式         | 触发时机         | 行为                               |
|--------------|------------------|------------------------------------|
| **按需搜索** | 遇到不会的       | Web 搜索 → 读文档 → 提取可用方案   |
| **类比迁移** | 方案 A 失败      | 搜索相似问题的解法，迁移到当前场景 |
| **实验验证** | 不确定哪个方案好 | 快速原型 → 跑 benchmark → 数据选方案 |

### 双层记忆系统

| 层级         | 生命周期   | 存什么                               |
|--------------|------------|--------------------------------------|
| **工作记忆** | 本次运行   | 当前状态、已尝试策略、临时假设       |
| **长期记忆** | 跨运行持久 | 验证过的解法模式、常见陷阱、领域知识 |

## 4. 资源预算层 — 成本感知 + 双模型路由

### 双模型分工

| 任务类型            | 推荐模型        | 成本对比         |
|---------------------|-----------------|------------------|
| S 级：简单编辑      | Haiku           | Opus 的 **1/60** |
| M 级：标准开发      | Sonnet          | Opus 的 **1/5**  |
| L/XL 级：架构规划   | Opus            | 基准             |
| 子任务：编辑类      | Sonnet 或 Haiku | 大幅降低         |

```python
# Claude Code 落地
# Agent(model="sonnet", prompt="Execute edit: ...")
# Agent(model="haiku", prompt="Rename variable: ...")
```

### 预算策略（已落地）

`persistent-solve.py` 的 DAG 模式已实现实际费用追踪和预算控制：

```bash
python scripts/persistent-solve.py "目标" --max-budget-usd 5.0 --per-task-budget 0.5
```

| 机制 | 实现方式 |
|------|----------|
| 费用追踪 | `claude -p --output-format json` 返回 `total_cost_usd` |
| 总预算熔断 | BudgetTracker 累计所有子任务费用，达到 `--max-budget-usd` 即停止 |
| 单任务预算 | `--max-budget-usd` 参数传给每个 `claude -p` 调用 |
| 线程安全 | threading.Lock 保护并行执行时的费用累计 |

### 上下文压缩应对

1. **关键信息外化** — 每完成一批子任务，把关键状态写到文件
2. **检查点摘要** — 防止早期信息丢失
3. **重型工作隔离** — 搜索/分析交给子 Agent，避免污染主对话上下文

## 5. 安全网层 — 检查点 + 回滚 + 回归验证

```python
for task in ready_tasks:
    checkpoint = save_state()  # git commit

    result = execute(task)
    regression = verify_completed(completed_tasks)

    if regression.failed:
        rollback(checkpoint)
        strategy = plan(task, constraints=[
            f"Must not modify {regression.broken_module}",
            f"Must keep {regression.broken_test} passing"
        ])
    elif result.success:
        completed_tasks.append(task)
    else:
        rollback(checkpoint)
```

### Lint/Test 自动反馈闭环

```
编辑 → 自动 lint+test → 失败？→ 错误输出自动注入 AI 上下文 → AI 自动修 → 再跑
  ↑                                                                    ↓
  └────────────────── 循环直到通过 ──────────────────────────────────────┘
```

配置：Hooks + `scripts/lint-feedback.sh`。详见 `../template/.claude/settings.json`。

## 6. 验证质量层 — 三级验证

| 级别          | 验证方式                                         | 适用场景     | 成本 |
|---------------|--------------------------------------------------|--------------|------|
| **L1 自检**   | 执行者自己的 verify()                            | 常规子任务   | 低   |
| **L2 对抗**   | **多 Agent 对抗循环**：Reviewer ↔ Executor 收敛  | 关键路径任务 | 中   |
| **L2-Alt**    | **测试对抗循环**：Tester 写破坏性测试 ↔ Executor 修 | 核心路径 | 中   |
| **L3 端到端** | 从用户原始目标出发，跑完整场景验证               | 最终交付前   | 高   |

### L2 多 Agent 对抗循环

不是一次性审查，而是 **Reviewer ↔ Executor 的收敛循环**：

```
Reviewer Agent (sonnet)  ← 审查 diff，提出问题清单
    │ PASS → 进入 L3
    │ ISSUES ↓
Executor Agent (sonnet)  ← 修复每个问题，commit
    │
    └→ 回到 Reviewer，重新审查（最多 3 轮）
```

关键路径还可叠加 **测试对抗循环**：Tester Agent 写边界/破坏性测试 → Executor 让测试通过 → Tester 再出新测试 → 循环直到稳定。

> 具体 prompt 模板和执行细节见 `/deep-task` 命令 Phase 4。

## 7. 元控制层 — 知道自己在干什么

### 分级升级机制

| 级别    | 触发条件            | 行为                                     |
|---------|---------------------|------------------------------------------|
| Level 0 | 信心 > 0.8          | 全自动执行，仅记录日志                   |
| Level 1 | 信心 0.5~0.8        | 通知人类进展，继续执行                   |
| Level 2 | 信心 0.3~0.5        | 给出 2~3 个选项，让人类选择方向          |
| Level 3 | 信心 < 0.3 或超预算 | 完整交接：进度 + 已尝试记录 + 建议下一步 |

### 元学习 — 越用越聪明

从历史执行轨迹中提炼元策略，存入 `memory/meta_*.md`，让系统自适应不同类型的问题。

元策略影响的决策点：

| 决策点   | 默认行为           | 元学习优化后                                 |
|----------|--------------------|----------------------------------------------|
| 分解粒度 | 固定粒度           | 根据问题类型自适应（探索型粗分，实施型细分） |
| 搜索深度 | 每次都广泛搜索     | 熟悉领域跳过搜索，陌生领域深度搜索           |
| 验证级别 | 按关键路径选 L1/L2 | 根据历史误判率动态调整                       |
| 策略排序 | LLM 默认排序       | 优先选历史上对同类问题成功率最高的策略       |

### 元策略文件格式

```markdown
---
name: meta_{problem-domain}
description: Meta-strategy for {domain} tasks
type: feedback
---

## {Problem Domain} Tasks

### Best Strategies
- {insight-1} (success rate: X%)

### Verification Level
- Recommend L{N}, because {reason}

### Last Validated
- Date: YYYY-MM-DD
- Result: {specific-result}
```

更新时机：L/XL 任务完成后分析轨迹 → 验证日期超 30 天时标记待验证 → 策略矛盾时保留最近验证版本。

---

## Claude Code 落地映射

> 以下映射已封装为 `/deep-task` 命令（`template/.claude/commands/deep-task.md`），可在 Claude Code 中直接使用。

| 框架层              | Claude Code 实现                 | 具体操作                                                 |
|---------------------|----------------------------------|----------------------------------------------------------|
| 入口分流 + 模型路由 | 对话开始时分析目标               | 判断 S/M/L/XL 级别 → 选路径 + 选模型                     |
| 代码地图            | `scripts/repo-map.py`            | L/XL 任务前生成 `.repo-map.json`                         |
| 目标审查            | `AskUserQuestion`                | 信心不足时弹出选项让用户选择                             |
| 目标分解 (DAG)      | `claude -p` + JSON 解析          | `/deep-task`: Agent 工具; `persistent-solve.py`: 独立 claude -p 调用返回 JSON DAG |
| 并行执行            | `Agent()` 或 `ThreadPoolExecutor`| `/deep-task`: 多 Agent 并行; `persistent-solve.py`: 进程级并行  |
| 并行隔离            | 文件冲突检测                     | 无冲突→并行; 有冲突或文件列表为空→串行（安全优先）       |
| 检查点              | `git commit`                     | `git commit -m "checkpoint: {task_name}"`                |
| 回滚                | `git revert` / `git checkout`    | 精确回滚到上一个检查点                                   |
| Lint/Test 反馈闭环  | Hooks + `lint-feedback.sh`       | 编辑 → 自动 lint/test → 失败自动反馈 → AI 自动修         |
| 对抗验证 (L2)       | `Agent(prompt="as a critic...")` | 独立子 Agent 用边界条件和反例挑战结果                    |
| 双模型分工          | `Agent(model="sonnet/haiku")`    | 编辑类子任务用 Haiku，标准任务用 Sonnet，规划用 Opus     |
| 工作记忆            | 对话上下文 + `TaskList`          | Task 工具追踪当前状态                                    |
| 长期记忆            | `~/.claude/projects/*/memory/`   | 验证过的模式存为 memory 文件                             |
| 元策略存储          | `memory/meta_*.md`               | 按问题域索引                                             |
| 分级升级            | `AskUserQuestion`                | 根据信心值选择 Level 0-3                                 |
| 费用追踪            | `--output-format json` 解析      | 每个子任务精确追踪 cost_usd、input/output tokens         |
| 预算熔断            | `BudgetTracker`                  | `--max-budget-usd` 总预算 + `--per-task-budget` 单任务预算 |
| 断点续传            | WIP 机制（Legacy 模式）          | 预算耗尽/升级时自动保存 WIP 文件                         |
| 上下文保护          | 子 Agent 隔离 + 检查点摘要       | 重型搜索交给子 Agent，定期生成进度摘要                   |

---

## 常见场景速查

### 修一个 bug（通常 M 级）

定位 → 确认根因 → 先写回归测试（TDD）→ 检查点 → 修复 → 跑测试 → L1 验证

### 新增功能模块（L 级）

目标审查 → DAG 分解（数据层→逻辑层→接口层→测试）→ 预检 → 逐个执行 + 检查点 → L2 验证 → L3 验证 → 元学习

### 性能优化（L 级）

目标审查（场景？平均还是最低？）→ Profiler → 方案设计 → 实施（可并行）→ L2 验证（不同场景达标？）→ L3 benchmark → 元学习

### 任务中断

保存 WIP（轨迹 + 残值 + 剩余任务 + 建议下一步）→ 下次从 WIP 恢复

---

## 踩坑记录

| 踩坑 | 对策 |
|-------|------|
| 所有任务都走完整流程 | 第一步永远是判定复杂度。S 级直接执行 |
| 分解粒度不对 | 探索型粗分，边做边细化；实施型细分，每个 ≤5 分钟 |
| 忘了回归验证 | 配置 Hooks 自动跑测试。至少每个子任务后跑一次 |
| 长对话丢失早期信息 | 每 3-5 个子任务写检查点摘要。预算过半时强制外化 |
| 方案失败后从头来过 | 萃取残值。失败中有排除的假设、可复用的代码 |
| 元策略只存在脑子里 | L/XL 完成后立即更新 `memory/meta_*.md` |

---

## 核心原则

入口先分流选模型，简单任务走快速路径。代码地图先扫描，规划时查地图不盲搜。目标先审查再分解，分解要预检防方向错。并行要检测冲突防踩踏（空文件列表视为潜在冲突），失败要萃取残值防浪费。编辑后 lint/test 自动闭环，失败自动修复不等人。验证要分级防盲区，执行要留轨迹防黑盒。贵模型做规划，便宜模型做编辑，成本省六成。**资源预算已落地**——`persistent-solve.py` 通过 `--output-format json` 精确追踪每个子任务的实际费用，`--max-budget-usd` 总预算 + `--per-task-budget` 单任务预算实现真正的费用熔断。上下文要外化防压缩丢失。检查点防级联故障，双层记忆防重复踩坑。元学习让系统越用越聪明，不在同一个地方低效两次。**不达目的不停止**——DAG 模式下每个子任务是独立的 `claude -p` 调用，预算耗尽或全部完成时精确停止。
