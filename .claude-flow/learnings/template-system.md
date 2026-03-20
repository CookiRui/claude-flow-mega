---
domain: template-system
entry_count: 1
last_pruned: 2026-03-20
---

### 2026-03-20 — 模板体系补齐（Agents/Hooks/Rules/REVIEW/CI） [score: 4]

- **Complexity**: estimated L, actual L (correct)
- **Strategies that worked**: T1-T5 全部并行 Agent 执行（5 个 sonnet agent 同时创建不同文件），显著提速
- **Strategies that failed**: 无
- **Pitfalls discovered**:
  - CI workflow 中用 shell 字符串拼接 JSON body 容易出 double-encoding bug，应统一用 `python3 -c json.dumps()` 一步生成完整 JSON
  - sub-agent 会自动 commit+push（因 constitution §4），需注意后续 commit 不会重复提交已推送的文件
  - install.py 和 bin/claude-autosolve.js 的 TEMPLATE_ITEMS 列表必须同步更新，容易遗漏
- **Verification notes**: L2 对抗审查发现 1 个 critical（CI JSON encoding），已修复
- **Cost**: ~$3.00 (7 sub-tasks, 3 commits)
