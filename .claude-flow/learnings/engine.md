---
domain: engine
entry_count: 1
last_pruned: 2026-03-20
---

### 2026-03-20 — /deep-task 引擎升级 + /upgrade 命令 + Skill 语义触发 [score: 4]

- **Complexity**: estimated L, actual L (correct)
- **Strategies that worked**:
  - 主上下文直接编辑 deep-task.md（多点插入同一文件），避免 agent 冲突
  - 新建文件委托 agent，编辑已有文件自己做
  - 验证级别自适应当场应用：本次任务是 config/docs 变更 → L1+L3 跳过 L2，节省了一轮 agent 调用
- **Strategies that failed**: 无
- **Pitfalls discovered**:
  - 插入新步骤后记得更新后续步骤编号（step 5→6→7），否则出现重复编号
  - cp 命令同步 .claude/ → template/ 比手动编辑两次更可靠，避免内容偏移
  - 文件编码问题：Windows 下 python3 读文件默认 GBK，含中文的文件需要指定 encoding='utf-8'
- **Verification notes**: 首次应用 Verification Level Selector，docs/config 变更跳过 L2 直接 L3，验证效率提升且无遗漏
- **Cost**: ~$2.50 (1 sonnet agent + main context edits)
