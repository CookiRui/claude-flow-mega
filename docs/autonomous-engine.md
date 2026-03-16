# 8 层自主执行引擎设计

核心是一个 **目标驱动的闭环**，由 8 层组成。但不是每个任务都需要走满 8 层——入口处先做复杂度分流。

## 入口：复杂度分级快速路径

80% 的日常任务不需要完整 8 层流程。入口处用轻量分类器决定走哪条路径，避免"杀鸡用牛刀"。

| 级别                | 判定条件                   | 走哪些层                         | 推荐模型         | 例子                     |
|---------------------|----------------------------|----------------------------------|------------------|--------------------------|
| **S（trivial）**    | 单文件、无依赖、可自动验证 | 直接执行 + L1 验证               | Haiku（快+便宜） | 重命名、格式修复、改注释 |
| **M（standard）**   | 2-5 文件、有明确验证条件   | 目标层 + 执行层 + 安全网 + L1/L2 | Sonnet（平衡）   | 增加 API、修 bug、加功能 |
| **L（complex）**    | 跨模块、涉及架构决策       | 全 8 层                          | Opus（强推理）   | 新子系统、性能优化       |
| **XL（strategic）** | 需要产品/战略层面判断      | 8 层 + 外部决策                  | Opus（强推理）   | 技术选型、架构重构       |

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

## 0. 目标审查层 — 先质疑目标本身（L/XL 级）

在投入任何资源之前，先判断目标是否合理。防止系统对不可能/模糊的目标耗尽预算。

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

**预判维度**：
- **物理可行性**：目标在技术/物理层面是否可达？
- **清晰度**：验证条件是否无歧义？
- **隐含 tradeoff**：达成目标需要牺牲什么？用户是否知情？
- **范围合理性**：目标与预算是否匹配？

## 1. 目标层 — 把模糊目标变成可验证的子任务 DAG

```
用户输入: "让游戏帧率稳定 60fps"
    ↓ 分解为 DAG（有向无环图），标注依赖关系
子目标 1: 定位性能瓶颈（验证条件: 输出 profiler 报告）
子目标 2: 针对 top3 瓶颈各出方案（验证条件: 每个方案有预期收益）  ← 依赖 1
子目标 3a: 实施方案 A + 回归测试（验证条件: benchmark 对比数据）  ← 依赖 2
子目标 3b: 实施方案 B + 回归测试（验证条件: benchmark 对比数据）  ← 依赖 2（可与 3a 并行）
子目标 4: 达标确认（验证条件: 连续 5 分钟 > 58fps）            ← 依赖 3a/3b
```

**关键设计**：
- 每个子目标必须带 **机器可判定的完成条件**，不能是"优化性能"这种模糊描述
- 子任务之间是 DAG 而非线性列表，无依赖的任务 **并行执行**
- **动态重规划**：每完成一批任务后，根据结果重新评估剩余任务是否仍然有效

### 分解预检 — 防止错误分解浪费所有后续努力

```
分解预检清单:
  □ 覆盖性: 所有子任务完成后，原始目标一定达成吗？有没有遗漏的环节？
  □ 独立性: 子任务之间的边界清晰吗？会不会出现"两个任务改同一处"的冲突？
  □ 可验证性: 每个验证条件是否真的能用工具自动判定？
  □ 粒度合理: 太粗（一个子任务包含太多不确定性）还是太细（管理开销大于执行收益）？
  □ 依赖正确: DAG 的依赖关系是否正确？有没有遗漏的隐式依赖？
```

## 2. 执行层 — Try → Evaluate → Adjust 循环

```
while not 目标达成 and 未超时 and 预算充足:
    1. 规划: 基于当前状态 + 长期记忆 + 元策略 + 残值，选择下一步行动
    2. 执行: 调用工具（搜索/编码/测试/部署）
    3. 观察: 收集执行结果
    4. 评估: 结果是否推进了目标？
       ├─ 是 → 保存检查点，回归验证已完成任务，继续
       ├─ 部分 → 调整方案，重试（换策略，不重复）
       └─ 否 → 回溯，萃取残值，尝试替代路径
    5. 学习: 记录"什么有效/什么无效"到工作记忆，提炼模式到长期记忆
```

**防死循环机制**：
- 同一策略最多尝试 N 次（N=2~3）
- 失败后必须 **换方法** 而非重试
- 设置总时间/总步数/总 token 上限
- 连续 K 次无进展 → 分级升级

### 并行冲突检测 — 防止并行任务互相踩踏

```python
ready = task_dag.get_ready_tasks()

# Conflict detection: which tasks touch the same resource?
groups = detect_conflicts(ready)

for group in groups:
    if len(group) == 1:
        execute(group[0])                    # No conflict, run directly
    elif can_isolate(group):
        parallel_execute_isolated(group)     # Each in isolated branch/sandbox, merge later
    else:
        sequential_execute(group)            # Cannot isolate, fall back to sequential
```

### 失败残值萃取 — 失败的尝试也有价值

```python
if not result.success:
    rollback(checkpoint)

    # Extract salvage: valuable artifacts from failure
    salvage = extract_salvage(result)
    # salvage may include:
    #   - Eliminated hypotheses ("not a memory leak, heap is stable")
    #   - Reusable utility code ("benchmark script already written")
    #   - Narrowed problem scope ("issue is in render pipeline, not logic layer")
    #   - Intermediate data (profiler results, log analysis)

    strategies_tried.append(FailedAttempt(
        strategy=strategy,
        reason=result.failure_reason,
        salvage=salvage
    ))
```

## 3. 知识层 — 自动学习的 3 种模式 + 代码地图

### 代码地图（Repo Map）— 借鉴 Aider

在大型代码库中，不知道"哪个类在哪个文件"会导致大量搜索试探，浪费 token。用 AST 解析 + 引用排序解决这个问题。

**核心思路**：在 L/XL 任务开始前，自动扫描代码库生成符号地图缓存，后续规划和执行时直接查地图定位文件。

```bash
# Generate repo map before L/XL tasks
python scripts/repo-map.py /path/to/project
# Outputs .repo-map.json for file/symbol lookup during planning
```

**收益**：
- 减少搜索试探，token 消耗降低 **50-70%**
- 文件定位准确率提升（不会漏掉间接依赖）
- DAG 分解时自动识别模块边界和依赖关系

### 知识获取的 3 种模式

| 模式         | 触发时机         | 具体行为                               |
|--------------|------------------|----------------------------------------|
| **按需搜索** | 遇到不会的       | Web 搜索 → 读文档 → 提取可用方案       |
| **类比迁移** | 方案 A 失败      | 搜索相似问题的解法，迁移到当前场景     |
| **实验验证** | 不确定哪个方案好 | 快速原型 → 跑 benchmark → 用数据选方案 |

### 双层记忆系统

| 层级         | 生命周期   | 存什么                               | 例子                                |
|--------------|------------|--------------------------------------|-------------------------------------|
| **工作记忆** | 本次运行   | 当前状态、已尝试策略、临时假设       | "方案 A 失败因为 X"                 |
| **长期记忆** | 跨运行持久 | 验证过的解法模式、常见陷阱、领域知识 | "Unity DrawCall 优化首选 SRP Batch" |

## 4. 资源预算层 — 成本感知执行 + 双模型路由

### 双模型分工 — 借鉴 Aider Architect/Editor

强模型做推理规划，快模型做编辑执行。同一个对话全程用 Opus 是浪费——改个变量名不需要 Opus 的推理能力。

| 任务类型            | 推荐模型        | 理由                             | 成本对比         |
|---------------------|-----------------|----------------------------------|------------------|
| S 级：简单编辑      | Haiku           | 不需要推理，快和便宜最重要       | Opus 的 **1/60** |
| M 级：标准开发      | Sonnet          | 需要一定推理但不需要最强         | Opus 的 **1/5**  |
| L/XL 级：架构规划   | Opus            | 需要深度推理、多步规划           | 基准             |
| 子任务：编辑类      | Sonnet 或 Haiku | 主 Agent 已规划好，子 Agent 执行 | 大幅降低         |

```python
# Claude Code actual usage
# Main Agent uses Opus for planning
# Agent(model="sonnet", prompt="Execute edit: ...")  Subagent uses Sonnet
# Agent(model="haiku", prompt="Rename variable: ...")  Simple edits use Haiku
```

**预算策略**：
```yaml
budget:
  total_token: 500k
  used: 120k
  per_step_limit: 50k       # Prevent one step from consuming all budget
  search_limit: 20
  time_limit: 30min
  strategy:
    budget > 50%: Normal mode (search + experiment + verify)
    budget 20~50%: Economy mode (prefer reusing known solutions, reduce searching)
    budget < 20%: Emergency mode (only highest-confidence actions, or escalate to human)
```

### 上下文压缩应对策略

Claude Code 在接近上下文窗口限制时会自动压缩历史消息。必须主动应对。

1. **关键信息外化** — 每完成一批子任务，把关键状态写到文件
2. **检查点摘要** — 防止早期信息丢失
3. **重型工作隔离** — 搜索/分析交给子 Agent，避免大量结果污染主对话上下文

## 5. 安全网层 — 检查点 + 回滚 + 回归验证

```python
for task in ready_tasks:
    checkpoint = save_state()  # git commit / snapshot

    result = execute(task)

    # Regression check: do previously passed tasks still pass?
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

### Lint/Test 自动反馈闭环 — 借鉴 Aider

```
旧方案（单向 Hooks）:
  编辑 → Hooks 跑 lint → lint 失败 → 用户看到错误 → 手动让 AI 修

新方案（双向闭环）:
  编辑 → 自动 lint+test → 失败？→ 错误输出自动注入 AI 上下文 → AI 自动修 → 再跑
    ↑                                                                    ↓
    └────────────────── 循环直到通过 ──────────────────────────────────────┘
```

配置方式：通过 Hooks + `scripts/lint-feedback.sh` 实现。详见 `../template/.claude/settings.json`。

## 6. 验证质量层 — 多视角校验

### 三级验证体系

| 级别          | 验证方式                           | 适用场景     | 成本 |
|---------------|------------------------------------|--------------|------|
| **L1 自检**   | 执行者自己的 verify()              | 常规子任务   | 低   |
| **L2 对抗**   | 独立 Agent 用不同输入/边界条件挑战 | 关键路径任务 | 中   |
| **L3 端到端** | 从用户原始目标出发，跑完整场景验证 | 最终交付前   | 高   |

```python
# L2: Adversarial verification — another Agent tries to find flaws
adversarial = spawn_critic_agent(task, result)
challenges = adversarial.find_issues(
    edge_cases=True,
    assumption_check=True,
    integration_risk=True
)
```

## 7. 元控制层 — 知道自己在干什么

元控制负责：
- **进度感知**：离目标还有多远
- **策略切换**：当前路径不通时，切到备选
- **资源监控**：预算是否健康
- **分级升级**：根据信心值决定人类介入程度
- **轨迹记录**：结构化记录每一步决策，供诊断和复盘
- **元学习**：从历史轨迹中优化自身执行策略

### 分级升级机制

| 级别    | 触发条件            | 行为                                     |
|---------|---------------------|------------------------------------------|
| Level 0 | 信心 > 0.8          | 全自动执行，仅记录日志                   |
| Level 1 | 信心 0.5~0.8        | 通知人类进展，继续执行                   |
| Level 2 | 信心 0.3~0.5        | 给出 2~3 个选项，让人类选择方向          |
| Level 3 | 信心 < 0.3 或超预算 | 完整交接：进度 + 已尝试记录 + 建议下一步 |

### 元学习 — 越用越聪明

从历史执行轨迹中提炼元策略，让系统自适应不同类型的问题。

```python
def meta_learn(trace: ExecutionTrace):
    insights = analyze_trace(trace)

    # Which strategies work best for which problem types?
    strategy_patterns = insights.strategy_effectiveness

    # Was budget allocation reasonable?
    budget_insights = insights.cost_vs_progress

    # Did verification levels match risk?
    verify_insights = insights.verify_effectiveness

    # Was decomposition granularity appropriate?
    decompose_insights = insights.granularity_effectiveness
```

元策略影响的决策点：

| 决策点   | 默认行为           | 元学习优化后                                 |
|----------|--------------------|----------------------------------------------|
| 分解粒度 | 固定粒度           | 根据问题类型自适应（探索型粗分，实施型细分） |
| 搜索深度 | 每次都广泛搜索     | 熟悉领域跳过搜索，陌生领域深度搜索           |
| 验证级别 | 按关键路径选 L1/L2 | 根据历史误判率动态调整                       |
| 策略排序 | LLM 默认排序       | 优先选择历史上对同类问题成功率最高的策略     |
| 预算分配 | 均匀分配           | 根据历史 ROI 倾斜分配                       |

### 元策略存储

存储在 `~/.claude/projects/{project}/memory/` 中的 `meta_*.md` 文件，按问题域索引。每次 L/XL 任务完成后自动更新。

## 8 层架构总览

```
┌───────────────────────────────────────────────────────────┐
│  目标审查层     可行性预判 / 歧义澄清 / tradeoff 告知     │
├───────────────────────────────────────────────────────────┤
│  目标层         模糊目标 → 可验证子任务 DAG + 分解预检     │
├───────────────────────────────────────────────────────────┤
│  元控制层       进度感知 / 分级升级 / 轨迹记录 / 元学习    │
├───────────────────────────────────────────────────────────┤
│  验证质量层     L1 自检 / L2 对抗验证 / L3 端到端          │
├───────────────────────────────────────────────────────────┤
│  资源预算层     token·时间·步数预算 + 自适应策略            │
├───────────────────────────────────────────────────────────┤
│  执行层         Try → Evaluate → Adjust + 冲突检测 + 残值  │
├───────────────────────────────────────────────────────────┤
│  安全网层       检查点 / 回滚 / 回归验证                   │
├───────────────────────────────────────────────────────────┤
│  知识层         按需搜索 / 类比迁移 / 双层记忆              │
└───────────────────────────────────────────────────────────┘
```

## Claude Code 落地映射

| 框架层              | Claude Code 实现                 | 具体操作                                                 |
|---------------------|----------------------------------|----------------------------------------------------------|
| 入口分流 + 模型路由 | 对话开始时分析目标               | 判断 S/M/L/XL 级别 → 选路径 + 选模型                     |
| 代码地图            | `scripts/repo-map.py`            | L/XL 任务前生成 `.repo-map.json`                         |
| 目标审查            | `AskUserQuestion`                | 信心不足时弹出选项让用户选择                             |
| 目标分解 (DAG)      | `TaskCreate` + `TaskList`        | 每个子任务创建 Task，标注依赖关系                        |
| 并行执行            | `Agent()` 多个并行调用           | 一条消息中同时发起多个 Agent 工具调用                    |
| 并行隔离            | `Agent(isolation="worktree")`    | 冲突任务各自在独立 worktree 中执行                       |
| 检查点              | `git commit`                     | `git commit -m "checkpoint: {task_name}"`                |
| 回滚                | `git revert` / `git checkout`    | 精确回滚到上一个检查点                                   |
| Lint/Test 反馈闭环  | Hooks + `lint-feedback.sh`       | 编辑 → 自动 lint/test → 失败自动反馈 → AI 自动修         |
| 对抗验证 (L2)       | `Agent(prompt="as a critic...")` | 独立子 Agent 用边界条件和反例挑战结果                    |
| 双模型分工          | `Agent(model="sonnet/haiku")`    | 编辑类子任务用 Haiku，标准任务用 Sonnet，规划用 Opus     |
| 工作记忆            | 对话上下文 + `TaskList`          | Task 工具追踪当前状态                                    |
| 长期记忆            | `~/.claude/projects/*/memory/`   | 验证过的模式存为 memory 文件                             |
| 元策略存储          | `memory/meta_*.md`               | 按问题域索引                                             |
| 分级升级            | `AskUserQuestion`                | 根据信心值选择 Level 0-3                                 |
| 断点续传            | WIP 机制                         | 预算耗尽/升级时自动保存 WIP 文件                         |
| 上下文保护          | 子 Agent 隔离 + 检查点摘要       | 重型搜索交给子 Agent，定期生成进度摘要                   |

## 核心原则

入口先分流选模型，简单任务走快速路径。代码地图先扫描，规划时查地图不盲搜。目标先审查再分解，分解要预检防方向错。并行要检测冲突防踩踏，失败要萃取残值防浪费。编辑后 lint/test 自动闭环，失败自动修复不等人。验证要分级防盲区，执行要留轨迹防黑盒。贵模型做规划，便宜模型做编辑，成本省六成。资源预算防烧钱，上下文要外化防压缩丢失。检查点防级联故障，双层记忆防重复踩坑。元策略要落地存储可索引，分级升级防死磕。元学习让系统越用越聪明，不在同一个地方低效两次。**不达目的不停止**——单会话预算耗尽不是终点，外层持久化循环自动从 WIP 恢复，继续推进直到目标达成或熔断。
