# claude-flow

让 Claude Code 拥有结构化项目认知 + 自主执行能力的开源框架。

## 项目结构

```
template/   -> 用户项目模板（CLAUDE.md、.claude/ 配置、.claudeignore）
scripts/    -> 工具脚本（持久化循环、代码地图、lint 反馈）
docs/       -> 方法论文档
bin/        -> npm CLI 入口（npx claude-autosolve init）
install.py  -> Python 一键安装脚本
tests/      -> 单元测试（pytest）
```

## 规则

- 任何修改完成后必须 commit 并 push 到 origin（https://github.com/CookiRui/claude-flow.git）
- `template/` 下的文件是用户模板，包含 `{placeholder}` 是正常的，不要替换
- README.md 的功能描述必须与 template/ 下的实际文件保持一致
