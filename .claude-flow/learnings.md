# Learnings

## 2026-03-19 — persistent-solve.py 原子化 DAG 调度器升级

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
- **Time**: 1 round, 7 sub-tasks (T1-T7)

## 2026-03-20 — 模板体系补齐（Agents/Hooks/Rules/REVIEW/CI）

- **Complexity**: estimated L, actual L (correct)
- **Strategies that worked**: T1-T5 全部并行 Agent 执行（5 个 sonnet agent 同时创建不同文件），显著提速
- **Strategies that failed**: 无
- **Pitfalls discovered**:
  - CI workflow 中用 shell 字符串拼接 JSON body 容易出 double-encoding bug，应统一用 `python3 -c json.dumps()` 一步生成完整 JSON
  - sub-agent 会自动 commit+push（因 constitution §4），需注意后续 commit 不会重复提交已推送的文件
  - install.py 和 bin/claude-autosolve.js 的 TEMPLATE_ITEMS 列表必须同步更新，容易遗漏
- **Verification notes**: L2 对抗审查发现 1 个 critical（CI JSON encoding），已修复。SessionStart matcher 的 warning 经验证为合理设计。
- **Time**: 1 round, 7 sub-tasks (T1-T7), 3 commits (2 by sub-agents + 1 final)
