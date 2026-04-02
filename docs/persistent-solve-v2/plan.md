# persistent-solve v2: 递归 DAG 编排引擎

## 1. Overview

### Goals

将 `scripts/persistent-solve.py` 从单层 DAG 调度器升级为**递归 DAG 编排引擎**，支持：

1. **递归拆解** — 按复杂度自动收敛（C≤2 停止，C≥3 继续递归），硬上限 `MAX_RECURSION_DEPTH=5`，直到所有叶子任务 ≤5 分钟
2. **原子提交** — 每个叶子任务产出一个独立 checkpoint commit，失败时标记 `[FAILED]`，不自动 revert
3. **契约文件** — 子 DAG 执行前生成接口契约，子任务 prompt 自动注入父级和兄弟的契约
4. **验证分级** — C:1-2 → L1，C:3-4 → L1+L2，C:5 → L1+L2+L3
5. **局部重规划** — 失败时只重新拆解失败节点及其下游
6. **看板输出** — 实时写 `kanban.json` + 终端树形进度

### Non-Goals

- Web UI 看板（JSON 输出即可，前端是独立项目）
- 多进程 Claude Code 实例协调（仍是单进程 + ThreadPoolExecutor）
- 自动 git revert（标记失败，用户决定回退）
- 替换 `/deep-task` 命令（persistent-solve 是跨会话脚本，deep-task 是会话内命令）

---

## 2. Affected Modules

| Module | Action | Description |
|--------|--------|-------------|
| `scripts/persistent-solve.py` | **重写** | 核心编排引擎 |
| `tests/test_persistent_solve.py` | **重写** | 配套测试 |
| `README.md` | **更新** | 新 CLI 参数和功能描述 |
| `Docs/persistent-loop.md` | **更新** | 文档同步 |

不新增文件，不新增依赖。运行时生成的文件：
- `.claude-flow/kanban.json` — 看板状态
- `.claude-flow/contracts/{dag-id}.md` — 契约文件（临时，任务完成后清理）

---

## 3. Data Model

### 3.1 RecursiveTask（替代原 Task）

```python
@dataclass
class RecursiveTask:
    id: str                        # 全局唯一 ID，层级用 "." 分隔：L0.T1.T2
    description: str
    acceptance_criteria: str
    dependencies: list[str]        # 同层任务 ID（全局唯一，由 recursive_plan 自动加 parent 前缀）
    files: list[str]
    complexity: int                # 1-5，驱动模型选择和验证级别。必须在 [1,5] 范围内
    status: str                    # pending | planning | running | done | failed | replanning
    depth: int                     # 当前递归深度（0=根）
    children: list[str]            # 子任务 ID 列表（空=叶子节点）
    parent: str | None             # 父任务 ID
    retries: int = 0
    max_retries: int = 2           # 注意：重试由执行层控制，DAG 层 mark_failed 无条件标记 failed
    cost_usd: float = 0.0
    commit_hash: str | None = None # 成功时记录 commit SHA
    error_summary: str | None = None
```

### 3.2 RecursiveDAG（替代原 TaskDAG）

```python
class RecursiveDAG:
    tasks: dict[str, RecursiveTask]  # 所有任务（包括各层级）
    
    def get_leaf_tasks() -> list[RecursiveTask]
    def get_ready_leaves() -> list[RecursiveTask]       # 叶子 + 依赖满足
    def get_children(task_id) -> list[RecursiveTask]
    def get_subtree(task_id) -> list[RecursiveTask]     # 任务及其所有后代
    def mark_done(task_id, commit_hash, cost_usd)
    def mark_failed(task_id, error_summary)             # 无条件标记 failed，不含重试逻辑
    def replace_subtree(task_id, new_children)           # 局部重规划，同时：
                                                         #   1. 删除旧契约文件
                                                         #   2. 将下游依赖重映射到新子树根 ID
    def propagate_status()                               # 子任务全 done → 父 done（带锁，防并行重复触发）
    def to_kanban_json() -> dict                         # 看板输出
    def get_parallel_groups(ready) -> (parallel, sequential)
```

### 3.3 Contract（契约文件）

```python
@dataclass
class Contract:
    dag_id: str            # 子 DAG 的根任务 ID
    inputs: list[str]      # 依赖的接口/数据
    outputs: list[str]     # 提供的接口/数据
    constraints: list[str] # 架构约束
    
    def to_markdown() -> str
    def save(base_dir: str)
    
    @staticmethod
    def load(path: str) -> "Contract"
```

### 3.4 KanbanState（看板状态）

```python
@dataclass
class KanbanState:
    goal: str
    start_time: str
    tree: dict               # 递归树结构，每个节点含 id/status/cost/children
    summary: dict             # {total, done, failed, pending, running, total_cost}
    
    def update_from_dag(dag: RecursiveDAG)
    def save(path: str)      # 写 JSON
    def print_tree()          # 终端树形输出
```

---

## 4. Flow Design

### 4.1 主流程

```
persistent_solve(goal, args)
  │
  ├─ Phase 0: clarify_goal()              [复用现有]
  │
  ├─ Phase 1: recursive_plan(goal)
  │    ├─ Claude 拆解 → 顶层任务列表（含 complexity 评分）
  │    ├─ 验证 complexity ∈ [1,5]，超范围 → 规划失败 → exit(1)
  │    ├─ Claude 返回的子任务 ID 自动加 parent 前缀（T1.task-1）防全局冲突
  │    ├─ 对每个 C≥3 的任务：递归调用 recursive_plan()
  │    ├─ 硬上限：depth > MAX_RECURSION_DEPTH(5) → 强制作为叶子执行
  │    ├─ 生成契约文件：.claude-flow/contracts/{task-id}.md
  │    └─ 返回 RecursiveDAG
  │
  ├─ Phase 2: execute_recursive_dag(dag)
  │    ├─ while dag.get_ready_leaves():
  │    │    ├─ 分组 parallel/sequential
  │    │    ├─ 执行叶子任务（带契约注入）
  │    │    ├─ L1 验证（每个叶子）
  │    │    ├─ checkpoint commit
  │    │    ├─ 更新 kanban.json
  │    │    ├─ propagate_status()
  │    │    └─ 对刚完成的分支节点：运行 L2/L3 验证
  │    │
  │    ├─ 失败处理（重试由执行层控制，DAG 层 mark_failed 无条件标记）：
  │    │    ├─ 执行层维护 retry_count，retries < max → 重新执行
  │    │    ├─ retries >= max → 局部重规划
  │    │    │    ├─ 收集失败上下文
  │    │    │    ├─ 重新拆解失败节点及下游
  │    │    │    ├─ replace_subtree()：删旧契约 + 重映射下游依赖 + 更新 DAG
  │    │    │    └─ 继续执行新子树
  │    │    └─ 重规划也失败 → dag.mark_failed() + commit "[FAILED]"，继续其他分支
  │    │
  │    └─ 预算/时间熔断检查（每轮）
  │
  └─ Phase 3: finalize()
       ├─ 最终状态报告
       ├─ 清理契约文件
       └─ 输出成本摘要
```

### 4.2 递归拆解流程

```
recursive_plan(goal_or_task, depth=0)
  │
  ├─ 调用 Claude: "拆解这个目标，给每个子任务评 complexity 1-5"
  ├─ 解析 JSON → RecursiveTask[]
  │
  ├─ 对每个任务:
  │    ├─ complexity ≤ 2 → 叶子节点，停止
  │    ├─ complexity ≥ 3 → 递归:
  │    │    ├─ recursive_plan(task.description, depth+1)
  │    │    ├─ 生成契约文件
  │    │    └─ 链接 parent/children
  │    └─ 标记 depth
  │
  └─ 返回所有任务（扁平化到 DAG）
```

### 4.3 验证流程

```
after_leaf_done(task):
    run_l1(task)  # 所有叶子任务

after_branch_done(parent_task):
    # 线程安全：propagate_status 使用 _lock 确保 after_branch_done 只触发一次
    if parent_task.complexity >= 3:
        run_l2(parent_task)  # 对抗审查：Review → Fix 循环
    if parent_task.complexity >= 5:
        run_l3(parent_task)  # 端到端验证
```

### 4.4 错误流程

```
on_task_failed(task, error):
    # 重试计数由执行层维护（不在 DAG 层）
    execution_retries[task.id] += 1
    if execution_retries[task.id] < task.max_retries:
        → 重新执行同一任务（status 仍为 pending）
    else:
        → dag.mark_failed(task.id, error)  # 无条件标记 failed
        → replan_subtree(task)
            ├─ 收集: 失败原因 + 已完成兄弟任务的契约
            ├─ Claude: "这个方案失败了({error})，请重新拆解"
            ├─ 解析新子任务
            ├─ dag.replace_subtree(task.id, new_children)
            └─ 继续执行
        
        if replan also fails:
            → task.status = "failed"
            → task.error_summary = error
            → commit with "[FAILED]" prefix
            → 继续执行其他无依赖的分支
```

---

## 5. Module Design

### 5.1 数据层（RecursiveTask + RecursiveDAG）

**职责**：DAG 数据结构、依赖解析、状态管理

**接口**：
```python
class RecursiveDAG:
    def __init__(self, tasks: list[RecursiveTask] = None)
    def add_task(self, task: RecursiveTask)
    def get_leaf_tasks(self) -> list[RecursiveTask]
    def get_ready_leaves(self) -> list[RecursiveTask]
    def get_children(self, task_id: str) -> list[RecursiveTask]
    def get_subtree(self, task_id: str) -> list[RecursiveTask]
    def get_parallel_groups(self, ready: list) -> tuple[list, list]
    def mark_done(self, task_id: str, commit_hash: str = None, cost_usd: float = 0.0)
    def mark_failed(self, task_id: str, error_summary: str = None)
    def replace_subtree(self, task_id: str, new_children: list[RecursiveTask])
    def propagate_status(self)
    def all_done(self) -> bool
    def summary(self) -> str
    def to_kanban_dict(self) -> dict
```

### 5.2 规划层（recursive_plan + replan_subtree）

**职责**：调用 Claude 进行递归拆解，生成契约文件

**接口**：
```python
def build_recursive_plan_prompt(goal: str, depth: int, parent_contract: str = None) -> str
def recursive_plan(goal: str, budget: BudgetTracker, depth: int = 0, parent_id: str = None) -> RecursiveDAG
def replan_subtree(task: RecursiveTask, dag: RecursiveDAG, error_context: str, budget: BudgetTracker) -> list[RecursiveTask]
```

**Claude prompt 变化**：新增 `complexity` 字段要求，输出格式：
```json
[{
  "id": "task-1",
  "description": "...",
  "acceptance_criteria": "...",
  "dependencies": [],
  "files": ["..."],
  "complexity": 3
}]
```

**解析规则**（`parse_recursive_dag_response`）：
- `complexity` 必须为 int 且 ∈ [1, 5]，否则该任务视为规划失败
- JSON 解析失败 → 不生成 fallback 叶子（v1 行为），而是抛出 `PlanningError`
- 调用方捕获 `PlanningError` 后：若 depth > 0 → 将该子树标记 failed 触发局部重规划；若 depth == 0 → exit(1)

**ID 命名空间**：
- `recursive_plan` 在插入全局 DAG 前，将 Claude 返回的 ID 自动加 parent 前缀
- 例：parent=`T1`，Claude 返回 `task-1` → 实际 ID 为 `T1.task-1`
- 根层级不加前缀（`T1`, `T2`, ...）

### 5.3 契约层（Contract）

**职责**：子 DAG 间的接口契约生成、加载、注入

**接口**：
```python
def generate_contract(task: RecursiveTask, dag: RecursiveDAG, budget: BudgetTracker) -> Contract
def load_relevant_contracts(task: RecursiveTask, dag: RecursiveDAG) -> str
def cleanup_contracts(base_dir: str)
```

**契约文件格式**：
```markdown
# Contract: {task-id}

## Inputs (what this module depends on)
- {interface/data description}

## Outputs (what this module provides)
- {interface/data description}

## Constraints
- {architectural constraints from parent}
```

### 5.4 执行层（execute_recursive_dag）

**职责**：按 DAG 调度叶子任务执行、验证、提交

**接口**：
```python
def execute_recursive_dag(dag: RecursiveDAG, goal: str, budget: BudgetTracker, kanban: KanbanState)
def execute_leaf_task(task: RecursiveTask, goal: str, budget: BudgetTracker, contracts: str) -> dict
def run_verification(task: RecursiveTask, level: str, budget: BudgetTracker) -> bool
def checkpoint_commit(task: RecursiveTask, success: bool) -> str  # returns commit hash
```

**task prompt 注入契约**：
```python
prompt = f"""...
## Context (from sibling/parent contracts)
{load_relevant_contracts(task, dag)}

## Your Sub-Task
{task.description}
...
"""
```

### 5.5 看板层（KanbanState）

**职责**：实时状态持久化 + 终端树形输出

**接口**：
```python
class KanbanState:
    def __init__(self, goal: str)
    def update_from_dag(self, dag: RecursiveDAG)
    def save(self, path: str = ".claude-flow/kanban.json")
    def print_tree(self)
```

**kanban.json 结构**：
```json
{
  "goal": "做一款大型游戏",
  "start_time": "2026-04-02T10:00:00",
  "updated_at": "2026-04-02T10:30:00",
  "summary": {
    "total": 25, "done": 12, "failed": 1, "running": 3, "pending": 9,
    "total_cost_usd": 2.34
  },
  "tree": [
    {
      "id": "T1", "description": "战斗系统", "status": "running",
      "complexity": 5, "cost_usd": 1.20,
      "children": [
        {"id": "T1.1", "description": "伤害计算", "status": "done", "complexity": 3,
         "commit": "abc1234", "cost_usd": 0.40, "children": [
            {"id": "T1.1.1", "description": "暴击公式", "status": "done", "complexity": 2,
             "commit": "def5678", "cost_usd": 0.15, "children": []},
            ...
          ]},
        {"id": "T1.2", "description": "护甲系统", "status": "running", ...}
      ]
    }
  ]
}
```

**终端树形输出**：
```
[running] 做一款大型游戏  ($2.34)
├─ [running] T1: 战斗系统  ($1.20)
│  ├─ [done] T1.1: 伤害计算  ($0.40)  abc1234
│  │  ├─ [done] T1.1.1: 暴击公式  ($0.15)  def5678
│  │  └─ [done] T1.1.2: 元素伤害  ($0.25)  ghi9012
│  ├─ [running] T1.2: 护甲系统  ($0.30)
│  └─ [pending] T1.3: 闪避判定
├─ [done] T2: UI 框架  ($0.80)  jkl3456
└─ [pending] T3: 存档系统
```

### 5.6 CLI 层

**新增参数**（向后兼容）：
```
--recursive          启用递归拆解（首版默认 False，显式 opt-in；稳定后翻转为 True）
--kanban             启用看板输出（默认 True）
--kanban-path PATH   看板 JSON 路径（默认 .claude-flow/kanban.json）
--verify-level auto|l1|l2|l3  验证级别（默认 auto = 按复杂度分级）
```

---

## 6. Test Plan

TDD 循环列表，每个测试 ≤5 分钟：

### 6.1 RecursiveTask / RecursiveDAG

1. **[TDD]** RecursiveTask 创建和字段默认值
2. **[TDD]** RecursiveDAG.get_leaf_tasks — 区分叶子和分支节点
3. **[TDD]** RecursiveDAG.get_ready_leaves — 叶子 + 依赖满足
4. **[TDD]** RecursiveDAG.get_children / get_subtree — 层级查询
5. **[TDD]** RecursiveDAG.mark_done + propagate_status — 子全 done → 父 done
6. **[TDD]** RecursiveDAG.mark_failed — 标记失败 + 重试计数
7. **[TDD]** RecursiveDAG.replace_subtree — 局部替换子树
8. **[TDD]** RecursiveDAG.get_parallel_groups — 文件冲突检测（复用现有逻辑）
9. **[TDD]** RecursiveDAG.to_kanban_dict — 树形结构输出

### 6.2 规划层

10. **[TDD]** build_recursive_plan_prompt — 包含 complexity 要求
11. **[TDD]** parse_recursive_dag_response — 解析含 complexity 的 JSON
12. **[TDD]** parse_recursive_dag_response — complexity 超范围 [1,5] → PlanningError
13. **[TDD]** parse_recursive_dag_response — JSON 解析失败 → PlanningError（不生成 fallback 叶子）
14. **[TDD]** 递归停止条件 — C≤2 不再递归
15. **[TDD]** 递归硬上限 — depth > MAX_RECURSION_DEPTH → 强制作为叶子
16. **[TDD]** ID 命名空间 — 子任务 ID 自动加 parent 前缀，全局无冲突
17. **[TDD]** 契约文件生成和加载
18. **[TDD]** replan_subtree — 局部重规划生成新子任务

### 6.3 执行层

19. **[TDD]** execute_leaf_task — prompt 包含父契约
20. **[TDD]** execute_leaf_task — prompt 包含已完成兄弟契约
21. **[TDD]** execute_leaf_task — 无契约时 prompt 正常
22. **[TDD]** checkpoint_commit — 成功/失败不同 commit message
23. **[TDD]** run_verification — 按复杂度选择验证级别
24. **[TDD]** 失败→重试→重规划 流程（执行层控制重试计数）
25. **[TDD]** replace_subtree 后 get_ready_leaves 返回正确结果（下游依赖重映射）

### 6.4 看板层

26. **[TDD]** KanbanState.update_from_dag — 从 DAG 生成看板数据
27. **[TDD]** KanbanState.save — JSON 文件输出
28. **[TDD]** KanbanState.print_tree — 终端树形格式

### 6.5 集成/CLI

29. **[TDD]** CLI 新参数解析 + 向后兼容
30. **[TDD]** BudgetTracker 复用（无变化，确认兼容）
31. **[TDD]** clarify_goal 复用（无变化，确认兼容）

---

## 7. Constitution Compliance Audit

| Article | Compliance | Notes |
|---------|-----------|-------|
| §1: template/ 占位符 | ✅ N/A | 本次不修改 template/ |
| §2: README 同步 | ⚠️ 需要 | 新 CLI 参数需更新 README |
| §3: 零外部依赖 | ✅ | 仅使用标准库（dataclasses, json, subprocess, threading 等） |
| §4: commit + push | ✅ | 完成后 commit + push |
| §Session State | ✅ | 看板文件替代 session state 的作用 |

---

## 8. Key Design Decisions

### 8.1 为什么不用多进程并行？

现有 ThreadPoolExecutor 已经足够：每个 `claude -p` 调用本身是独立进程，Python 端只是调度。真正的并行瓶颈在 Claude API 的并发限制，不在本地。

### 8.2 为什么契约文件用 markdown 而非 JSON？

契约是注入到 Claude prompt 的，markdown 格式 Claude 理解最好，且人类可读。

### 8.3 为什么失败不自动 revert？

大型任务中，部分完成的代码仍然有价值。自动 revert 可能丢失可复用的工作。标记 `[FAILED]` + 保留 commit 历史，让用户基于全局视角决定回退范围。

### 8.4 递归深度为什么不设硬上限？

靠复杂度评分自动收敛（C≤2 停止）比硬上限更灵活。实践中大多数任务 2-3 层就会收敛。如果 Claude 持续给 C≥3，说明任务确实复杂，硬截断反而有害。

### 8.5 ID 命名规则

层级用 `.` 分隔：`T1` → `T1.task-1` → `T1.task-1.subtask-2`。好处：
- 从 ID 直接看出层级关系
- 排序自然呈现树结构
- git log 搜索 `checkpoint: T1.task-1` 能快速定位
- Claude 返回的短 ID 自动加 parent 前缀，避免全局冲突

---

## 9. Plan Review 修订记录

### 审查发现的 3 个 BLOCKER（已修复）

1. **无限递归风险** — 原方案不设递归深度硬上限。修复：增加 `MAX_RECURSION_DEPTH=5`，超过强制作为叶子执行。
2. **重试所有权冲突** — DAG 层 `mark_failed` 含重试逻辑，与执行层重试逻辑冲突。修复：DAG 层 `mark_failed` 无条件标记 failed，重试计数完全由执行层控制。
3. **规划失败静默吞没** — 解析失败时 fallback 生成 complexity=0 的叶子节点，静默执行。修复：complexity 必须 ∈ [1,5]，解析失败抛 `PlanningError`，不生成 fallback。

### 采纳的 5 个 WARNING

4. **ID 命名空间** — Claude 可能在不同递归层返回相同短 ID。修复：自动加 parent 前缀。
5. **replace_subtree 下游依赖** — 替换子树后下游依赖指向不存在的旧 ID。修复：replace_subtree 同时重映射下游依赖。
6. **replace_subtree 旧契约清理** — 替换子树时旧契约仍在磁盘。修复：replace_subtree 同时删除旧契约文件。
7. **replace_subtree 后 get_ready_leaves 测试** — 新增集成测试覆盖。
8. **propagate_status 线程安全** — 并行完成时可能重复触发 after_branch_done。修复：propagate_status 加锁。

### 采纳的 SUGGESTION

9. **--recursive 默认 False** — 首版显式 opt-in，稳定后翻转默认值。
10. **契约注入测试拆分** — execute_leaf_task 拆成 3 个独立测试。
