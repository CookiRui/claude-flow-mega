# 我如何让 Claude Code 从"每次犯同样的错"变成"可以信任的队友"

> 写了 20 多条规则的 CLAUDE.md，结果跨模块任务一来，Claude 还是该犯的错都犯。这篇文章讲我怎么彻底解决这个问题的。

---

## 痛点：AI 很聪明，但它不认识你的项目

我在做一个游戏项目，100 多个配置文件，严格的性能红线，自定义框架里到处是"AI 不知道就会写错"的约定。

每次开 Claude Code 新会话，同样的事情重复发生：

- **它不用我们的 ManagerCenter。** 我们所有系统都通过 ManagerCenter 注册——Claude 直接 `new`，每次都要纠正。
- **它在热路径里分配内存。** `Update()` 里写 `new List<>()`，这在 60fps 游戏里是致命的。
- **它用错日志库。** 我们封装了自己的 Logger——Claude 默认用 `Debug.Log`。
- **复杂任务做到一半就乱了。** 跨模块重构开头还行，中途丢失上下文，产出前后矛盾的代码。

我试过写一个超长的 `CLAUDE.md`，20 多条规则。小任务有用，但一旦涉及多个文件，Claude 还是会"忘"。

问题的本质是：**平面文档没有优先级，AI 无法区分"绝对不能违反"和"最好遵守"。**

## 解法：4 层渐进式配置

核心洞察：**不是所有上下文都需要每次加载。** 平面 CLAUDE.md 把一切塞进每次对话，浪费 token 还稀释了重要规则。

我设计了一个 4 层体系：

```
第 1 层：Constitution（宪法） — 每次对话都加载。4-7 条绝对不能违反的规则。
第 2 层：Rules（规则）       — 每次对话都加载。编码风格补充细则。
第 3 层：Skills（技能）      — 按需加载。只在任务匹配触发条件时才读取。
第 4 层：Commands（命令）    — 用户触发。多阶段复杂工作流。
```

### 第 1 层：宪法——"AI 不知道就一定会写错"的规则

每条规则带一对正确/错误代码示例：

```markdown
## §1: 所有系统必须通过 ManagerCenter 注册

​```csharp
// ✅ 正确
ManagerCenter.Register<IAuthService>(new AuthService());

// ❌ 错误 — Claude 的默认行为
var auth = new AuthService();
​```
```

**筛选标准**：把规则删掉，Claude 的默认行为还是对的？删掉它。用这个标准，我把 20 多条规则砍到了 5 条宪法条款。

**少就是多。** 5 条条款 Claude 每条都遵守；20 条规则它记住一半、忘掉一半。

### 第 2 层：Rules——编码风格细则

和宪法的区别：宪法放"绝对不能违反的架构约束"，Rules 放"最好这样写的风格细则"。比如：

```markdown
## Rule 1: 热路径里用 Span<T> 而不是数组拷贝 (per Constitution §3)
```

分开两层的好处：更新风格规则时不需要动宪法，降低维护成本。

### 第 3 层：Skills——省 token 的关键

Skills 是按需加载的参考文档。Claude 读触发描述，任务相关就加载，无关就跳过：

```markdown
---
name: custom-networking
description: "自定义 UDP 网络层。处理多人联机、数据包、NetManager 时加载。"
---
```

不触发 = 零 token 消耗。一个中型项目可能有 5-6 个 Skills，但单次对话通常只加载 1-2 个。

### 一键初始化：不用手填

最初我手写每个项目的宪法，很痛苦。后来做了 `/init-project` 命令：

```
claude
> /init-project
```

AI 自动扫描代码库，识别语言、框架、架构模式，生成所有 4 层配置。整个过程只需确认一次分析结果。

3 分钟搞定一个项目的配置，之前要 30-60 分钟。

## 自主引擎：让 Claude 自己完成复杂任务

配置系统解决了"Claude 做错事"的问题。但复杂任务还有三个痛点：

1. **中途丢上下文。** 大型重构做到一半，Claude 忘了前面做过什么。
2. **没有验证。** 它宣称"完成"，但测试是坏的。
3. **不学习。** 同样的错误在不同会话中反复出现。

所以我做了一个 8 层自主执行引擎 `/deep-task`：

```
Phase 0: 复杂度分类（S/M/L/XL）→ 简单任务走快速路径
Phase 1: 目标审查 — 可行吗？够清晰吗？
Phase 2: DAG 分解 — 拆成有依赖关系的子任务图
Phase 3: 并行执行 — 无冲突的任务同时跑
Phase 4: 三级验证
         L1: 每个子任务自检
         L2: Reviewer ↔ Executor 对抗循环（最多 3 轮）
         L3: 端到端集成验证
Phase 5: 元学习 — 记录什么策略有效，下次复用
```

Phase 0 很关键：不是每个任务都要走完 8 层——S 级任务（单文件、可自动验证）直接执行+提交，跳过整个引擎。Phase 5 把经验写入项目的 `learnings.md`，系统用得越多越聪明。

`/bug-fix` 也值得一提：它强制在修复之前先写回归测试，确保修的是根因而不是表象。

### 关键设计：Reviewer ↔ Executor 对抗循环

大多数"代码审查"prompt 是单次的："审查这个 diff。" 问题是审查者发现了问题，但没人修。

我的 L2 验证是一个**收敛循环**：

```
Reviewer Agent 审查 → 发现问题 → Executor Agent 修复 → commit →
Reviewer 重新审查 → 还有问题？→ Executor 再修 →
Reviewer 通过（或 3 轮后升级给用户）
```

**真实案例**：我用 `/deep-task` 升级了自己的 persistent-solve.py 脚本。L2 审查发现了 3 个 critical bug：

1. **线程安全**：BudgetTracker 在多线程并行执行时没有锁保护，`total_spent += cost` 不是原子操作
2. **异常吞噬**：并行任务中一个 `future.result()` 抛异常，剩余结果全部丢失，后续代码对 `None` 调用方法直接崩溃
3. **默认值错误**：`is_error` 字段默认为 `True`，导致所有正常响应被标记为失败

这三个 bug 如果跳过 L2，全部会上线。

## 预算控制：终于知道每个任务花了多少钱

Claude Code 会话没有费用可见性。你不知道一个任务花了多少钱，直到账单来。

我发现 `claude -p --output-format json` 会返回实际费用数据：

```json
{
  "total_cost_usd": 0.0537,
  "usage": { "input_tokens": 8698, "output_tokens": 4 },
  "duration_ms": 4078
}
```

于是我做了一个原子化调度器：把目标分解为子任务 DAG，每个子任务是独立的 `claude -p` 调用，全程追踪费用：

```bash
python scripts/persistent-solve.py "重构认证系统" --max-budget-usd 3.0

# 输出：
# Final budget summary:
#   Total spent: $1.2345 / $3.00
#     planning: $0.0800
#     task-1: $0.3200
#     task-2: $0.4500
#     task-3: $0.3845
#   Total time: 342s
```

无文件冲突的子任务自动并行。预算到了自动停止，不会多花一分钱。

## 效果

在 4 个项目上使用 3 个月后：

| 指标 | 之前 | 之后 |
|------|------|------|
| 每次会话违反架构约束 | 3-5 次 | <1 次（宪法显著降低违反率） |
| 声称"完成"但实际有 bug | ~30% | <5%（L2 兜住大部分） |
| 大任务中途丢上下文 | 频繁 | 罕见（DAG + 检查点） |
| 费用可见性 | 无 | 每个子任务精确追踪 |
| 新项目配置时间 | 30-60 分钟 | 3 分钟（`/init-project`） |

最大的收获不是某个数字——是**信任**。我现在把 L 级任务（跨模块重构、新子系统）交给 Claude Code，审查产出就行，不用全程手把手。

## 试试

```bash
npx claude-autosolve init
```

或者直接克隆：`git clone https://github.com/CookiRui/claude-flow.git && python install.py`

然后在 Claude Code 里：

```
/init-project
```

AI 自动分析你的项目，生成所有配置。没有占位符要填。

开源地址：[github.com/CookiRui/claude-flow](https://github.com/CookiRui/claude-flow)

如果你也在用 Claude Code 做正经项目，欢迎试试。踩到坑或者有改进建议，评论区见——这个框架还在持续迭代。

---

*一个被 Claude 反复犯同样错误折磨到崩溃的游戏开发者，写的自救框架。*
