# 原子化 DAG 调度 + 跨会话持久化循环

单次 Claude Code 会话有预算限制（token/时间/上下文窗口）。复杂任务做到一半预算耗尽怎么办？**不是停下来等人——而是自动恢复继续推进。**

---

## 与 `/deep-task` 的关系

| 方案 | 范围 | 适用场景 |
|------|------|----------|
| `/deep-task` | **单会话内**：DAG 分解 → 并行 Agent → 三级验证 → 元学习 | 大多数 L 级任务，单会话可完成 |
| `persistent-solve.py` | **跨会话**：原子化 DAG 调度，每个子任务独立 claude -p 调用 | XL 级任务，需要预算控制和费用追踪 |

它们是互补的：`/deep-task` 是会话内的执行引擎，`persistent-solve.py` 是会话间的原子化调度器。大多数情况下 `/deep-task` 足够，只有真正超大的任务才需要外层调度。

---

## 两种执行模式

### DAG 模式（默认）

每个子任务是独立的 `claude -p` 调用，脚本在外部做 DAG 调度。

```
┌─────────────────────────────────────────────────────────────┐
│  persistent-solve.py（外部调度器）                            │
│                                                             │
│  1. claude -p "分解目标为 JSON DAG"  ← 规划阶段             │
│       ↓ 解析 JSON，构建 TaskDAG                             │
│  2. 取出无依赖的子任务                                       │
│       ├─ 无文件冲突 → 多进程并行执行                         │
│       └─ 有冲突 → 串行执行                                  │
│  3. 每个子任务: claude -p "执行 T1: ..." --max-budget-usd X │
│       ↓ 解析 JSON 返回值，获取 cost/tokens/status           │
│  4. 标记完成/失败，检查预算，继续下一批                      │
│  5. 所有任务完成或熔断 → 输出费用汇总                        │
└─────────────────────────────────────────────────────────────┘
```

**关键特性**：
- 每个 `claude -p` 调用使用 `--output-format json` 获取 `total_cost_usd`、`usage`、`stop_reason`
- 每个调用使用 `--max-budget-usd` 限制单任务费用
- BudgetTracker 累计所有子任务费用，达到总预算即熔断
- ThreadPoolExecutor 进程级并行执行无文件冲突的子任务
- 线程安全的费用累计（threading.Lock）

### Legacy 模式

原始行为：每轮一个完整 Claude 会话，通过 WIP 文件握手。

```
┌─────────────────────────────────────────────────────────────┐
│  persistent-solve.py（外部调度器）                            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  claude -p "完整目标 + WIP 上下文"                     │  │
│  │  在预算和上下文范围内尽力推进                           │  │
│  │  遇到硬约束 → 保存 WIP → 退出                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  读取 .claude-flow/wip.md → 判断状态 → 注入下一轮 prompt    │
│  ├─ done → 完成                                             │
│  └─ active → 启动新会话，继续推进                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 使用方式

```bash
# DAG 模式（默认）— 原子化执行 + 预算追踪
python scripts/persistent-solve.py "Stabilize game frame rate at 60fps"
python scripts/persistent-solve.py "Refactor auth system" --max-budget-usd 3.0 --per-task-budget 0.3

# Legacy 模式 — 原始 WIP 握手循环
python scripts/persistent-solve.py "Fix memory leak" --mode legacy

# 通用选项
python scripts/persistent-solve.py "Goal" --max-rounds 5 --max-time 3600
```

### CLI 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `goal` | (必填) | 要达成的目标 |
| `--mode` | `dag` | 执行模式：`dag`（原子化子任务）或 `legacy`（WIP 握手） |
| `--max-budget-usd` | 5.0 | 总预算上限（美元） |
| `--per-task-budget` | 0.5 | 单个子任务预算上限（美元） |
| `--max-rounds` | 10 | 最大轮次 |
| `--max-time` | 7200 | 最大总时间（秒，默认 2 小时） |

---

## 熔断保护

| 熔断条件 | DAG 模式 | Legacy 模式 |
|----------|----------|-------------|
| 总预算耗尽 | `--max-budget-usd`，实际费用追踪 | `--max-budget-usd`，实际费用追踪 |
| 单任务预算 | `--per-task-budget`，每个 claude -p 调用限制 | `--per-task-budget`，每轮限制 |
| 最大轮次 | 10 | 10 |
| 最大总时间 | 2 小时 | 2 小时 |
| 连续无进展 | N/A（DAG 任务有明确完成/失败状态） | 3 轮 WIP 无变化 |
| 子任务重试 | 每个子任务最多重试 2 次后标记失败 | N/A |

---

## DAG 模式详解

### 规划阶段

脚本调用 `claude -p` 让 Claude 分解目标为 JSON DAG：

```json
[
  {
    "id": "task-1",
    "description": "Set up data models",
    "acceptance_criteria": "Types defined, imports work",
    "dependencies": [],
    "files": ["src/models.py"]
  },
  {
    "id": "task-2",
    "description": "Implement core logic",
    "acceptance_criteria": "Unit tests pass",
    "dependencies": ["task-1"],
    "files": ["src/service.py", "tests/test_service.py"]
  }
]
```

### 执行调度

```python
while dag.has_ready_tasks():
    if not budget.can_afford():
        break  # 预算熔断

    ready = dag.get_ready_tasks()           # 依赖已满足的任务
    parallel, sequential = dag.get_parallel_groups(ready)

    # 无文件冲突 → ThreadPoolExecutor 并行
    # 有冲突或文件列表为空 → 串行（安全优先）

    for task, result in executed:
        budget.record(task.id, result["cost_usd"])
        if result["success"]:
            dag.mark_done(task.id)
        else:
            dag.mark_failed(task.id)  # 自动重试最多 2 次
```

### 费用追踪

每个 `claude -p --output-format json` 调用返回：

```json
{
  "total_cost_usd": 0.0537,
  "usage": { "input_tokens": 3, "output_tokens": 4 },
  "duration_ms": 4078,
  "stop_reason": "end_turn",
  "is_error": false
}
```

脚本解析后累计到 BudgetTracker，最终输出：

```
Final budget summary:
  Total spent: $1.2345 / $5.00
    planning: $0.0800
    task-1: $0.3200
    task-2: $0.4500
    task-3: $0.3845
  Total time: 342s
```

### 失败处理

- 单个子任务失败 → 自动重试（最多 2 次），换不同策略
- 所有子任务失败 → 下一轮重新规划 DAG，注入失败上下文
- 预算耗尽 → 停止，输出已完成和待完成的任务列表

---

## Legacy 模式：WIP 机制

WIP（Work In Progress）是 Legacy 模式的状态存储格式。**固定路径：`.claude-flow/wip.md`**。

脚本和 Claude 之间通过这个文件"握手"：
- 脚本在 prompt 中告诉 Claude WIP 文件路径
- Claude 在每轮结束前写入进度
- 脚本读取 WIP 判断状态，并注入下一轮 prompt

### WIP 文件格式

```yaml
---
status: active              # active | need_human | done
goal: "目标描述"
round: 3                    # 当前第几轮
---

## Completed
- [x] 定位瓶颈（DrawCall 40%, GC 25%, Physics 15%）
- [x] 优化 DrawCall（800 → 320）

## Remaining
- [ ] 优化 GC（依赖: 无）
- [ ] 优化 Physics（依赖: 无）
- [ ] 最终验证（依赖: GC, Physics）

## Strategies Tried
- DrawCall: SRP Batcher 失败（Built-in RP）→ 残值: 确认渲染管线类型
- DrawCall: Static/Dynamic Batching 成功

## Constraints
- 不能切换渲染管线
- 不能降低画质

## Next Steps
1. 优先处理 GC（占比 25%，预期收益最大）
2. 搜索 GC 优化最佳实践
```

### 状态判断优先级

1. **WIP status 字段** — `done` / `need_human` / `active`（主要依据）
2. **WIP [x] 计数变化** — 判断是否有实际进展
3. **WIP 内容变化** — 兜底检测
4. **stdout 中的标记** — `[GOAL_ACHIEVED]` 作为最后 fallback

---

## 内层自救机制（Legacy 模式）

当某个子任务多次失败时，内层会尝试 3 级自救：

```
失败 → 自救 1: 换一个完全不同的角度
  ↓ 仍失败
      → 自救 2: 把当前子任务拆得更细
  ↓ 仍失败
          → 自救 3: 深度搜索学习后重试
  ↓ 仍失败
              → 保存 WIP，标记 [NEED_HUMAN]
```

只有所有自救手段都用尽后，才会标记需要人类介入。

---

## 实际落地方式

| 方案 | 实现 | 自动化程度 | 费用追踪 |
|------|------|------------|----------|
| **DAG 模式** | `persistent-solve.py`（默认） | 全自动 | 每任务精确追踪 |
| **Legacy 模式** | `persistent-solve.py --mode legacy` | 全自动 | 每轮追踪 |
| **GitHub Actions** | Push WIP 后触发 Action | 全自动 | 需自行配置 |
| **手动恢复** | 人工在 Claude Code 中 `Resume WIP` | 手动 | 无 |

**推荐**：DAG 模式用于需要预算控制的任务，Legacy 模式用于需要深度上下文连续性的任务。
