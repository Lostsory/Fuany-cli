# mini-claude-code

一个**忠实的最小可用 coding agent** —— 不依赖任何 agent 框架(LangChain 等),纯 Python + DeepSeek(OpenAI 兼容)裸写核心循环。在此前手撸的 Claude Code 检索内核最小版(`../phase-4-ai/agent_search.py`)基础上,对照 Claude Code / Hermes 真实源码逐步扩展。

> 不是克隆。是"看着真源码,把最小 agent 升级成最小可用 coding agent",并诚实标注哪些故意没做。

## 为什么裸写、不用框架

读过 Claude Code 与 Hermes 源码确认:二者都**不用 LangChain** —— agent 循环就是产品本体,框架抽象会遮蔽真实且 churn。本项目沿用同一取舍:核心循环自己拥有。

## 路线(MVP = T1 + subagent)

- [ ] **D1 工具注册表** — 工具=name+desc+schema+handler,一处注册(对照 CC Tool 注册 + Hermes registry「注册≠暴露」)
- [ ] **D2 文件工具集** — write / edit / glob / bash
- [ ] **D3 权限门** — 有副作用工具执行前确认;拒绝→作为 tool_result 回喂自我纠错
- [ ] **D4 交互 REPL + 流式** — 多轮对话 + 打字机输出(+ Ctrl-C 优雅中断)
- [ ] **D5 token 预算终止** — 去掉硬编码 MAX_STEPS,改累计 token 预算优雅停(对照 Hermes IterationBudget)
- [ ] **D6 subagent** — Task 工具:为子任务 spawn 独立 context 子 agent,只回传结果
- [ ] (可选,MVP 后)D7 SQLite 会话持久化 + resume —— 体现"agent≠脚本"
- [ ] (可选,MVP 后)skill(SKILL.md 渐进披露)

## 故意不做(诚实边界 = 判断力体现)

MCP(真协议,最重)· cron/kanban · gateway 多平台 · profile/config 隔离 · 完整 Curator · 上下文压缩 · 插件系统 · TUI

## 栈

Python 3 · DeepSeek(`openai` SDK,OpenAI 兼容)· `python-dotenv` · 无 agent 框架

## 运行

```bash
cp .env.example .env   # 填 DEEPSEEK_API_KEY
uv run python mini_cc.py
```

## 状态

🚧 脚手架完成,D1 进行中。完整构建计划见个人笔记 `项目-mini-claude-code`。
