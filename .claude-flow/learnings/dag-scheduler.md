---
domain: dag-scheduler
entry_count: 1
last_pruned: 2026-03-20
---

### 2026-03-19 — persistent-solve.py 原子化 DAG 调度器升级 [score: 5]

- **Complexity**: estimated L, actual L (correct)
- **Strategies that worked**: T1/T2/T3 并行开发（互不依赖的基础组件），L2 对抗审查发现 3 个 critical bug
- **Strategies that failed**: 无
- **Pitfalls discovered**:
  - `is_error` 字段默认值必须是 False 而非 True，否则正常响应被误判为失败
  - BudgetTracker 在 ThreadPoolExecutor 下需要 threading.Lock 保护
  - execute_parallel 中 future.result() 未捕获异常会导致剩余结果丢失
  - 空 files 列表的任务不能假设无冲突，应走串行
  - 变量 goal 在循环中被修改后，continuation hint 打印出错误的命令
- **Verification notes**: L2 对抗审查非常有价值，发现了 3 个会导致运行时崩溃的 critical bug + 4 个 warning
- **Cost**: ~$2.00 (7 sub-tasks)
