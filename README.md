# mini-claude-code

一个**不依赖任何 agent 框架**(LangChain / LlamaIndex 等)、纯 Python 裸写的最小可用 coding agent。核心循环自己拥有,逐特性对照 [Claude Code](https://claude.com/claude-code) 与 Hermes(Nous Research)真实源码实现,并**诚实标注哪些故意没做**。

> 不是克隆,是"读真源码 → 理解每个特性为什么这么设计 → 用最小代码忠实复刻 → 想清楚哪些该简化、哪些该砍"。每个特性都能讲清它在 CC/Hermes 源码的哪里、我为什么这么简化。

后端用 DeepSeek(OpenAI 兼容协议),换 provider 只改一行。

---

## 为什么裸写、不用框架

读 Claude Code 与 Hermes 源码后确认:**二者都不用 LangChain**。Agent 循环就是产品本体 —— "调模型 → 有工具调用就执行并回喂 → 没有就结束"这个 while 循环,框架抽象只会遮蔽它且随版本漂移。本项目沿用同一取舍:**核心循环自己拥有,看得见、改得动**。

---

## 快速开始

```bash
# 1. 配置 API key
echo "DEEPSEEK_API_KEY=sk-..." > .env

# 2. 跑(交互式 REPL)
uv run python mini_cc.py
```

进入后像 `claude` 一样多轮对话。`exit` / `quit` / Ctrl-D 退出。

可选环境变量(均有默认值,见 `config.py`):

| 变量 | 默认 | 作用 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | DeepSeek 凭证(必填) |
| `MINI_CC_MAX_TURNS` | 90 | 父 agent 单轮最大迭代数 |
| `MINI_CC_MAX_TURNS_SUBAGENT` | 50 | 子 agent 最大迭代数 |
| `MINI_CC_MAX_SUBAGENT_DEPTH` | 2 | 子 agent 最大递归深度 |
| `MINI_CC_MAX_PARALLEL` | 10 | read-only 工具并行最大并发 |

---

## 架构

```
用户输入
   │
   ▼
agent_answer()  ── 核心循环(对照 CC src/query.ts queryLoop)
   │   调模型(流式) → 拿 tool_calls → 执行 → 结果回喂 → 再调模型
   │   直到模型不再要工具(completed)/ 撞 max_turns / context 超限
   │
   ├─ 流式打字机输出 + DeepSeek reasoning round-trip
   ├─ token 二维记账(billed 计费 vs context 占用)
   ├─ grace call(撞顶前一轮提醒模型收尾)
   └─ 工具派发
         │
         ▼
   registry.call_tool()  ── 权限门 + mod-time 守卫 + 防御性派发
         │
         ▼
   tools/  ── read_file / grep / glob / write / edit / bash / task
```

| 模块 | 职责 |
|---|---|
| `mini_cc.py` | 入口 + 核心 agent 循环 + 流式 + 终止判定 + 并发调度 |
| `registry.py` | 工具注册表(一处声明,schema 与派发都从此派生)+ 权限门 |
| `config.py` | 所有 env 读取的单一入口(fail-loud + 类型化常量) |
| `llm.py` | LLM 构造(client + model + context_window 捆绑,一处切 provider) |
| `state.py` | per-agent 文件读状态(ContextVar 栈式隔离) |
| `tools/` | 工具实现,`import tools` 即触发自动注册 |
| `demos/` | 概念教学 demo(如 `contextvar_demo.py` 演示父子状态隔离) |

---

## 特性 × 源码对照(receipts)

每个特性都对照真源码实现,不凭想象:

| 特性 | 实现 | 对照源码 |
|---|---|---|
| 工具注册表(声明=派生) | `registry.py` `@register` | CC `Tool.ts` · Hermes `tools/registry.py`(注册≠暴露) |
| mod-time 守卫(防外部偷改) | `tools/files.py` write/edit | CC `FileWriteTool.ts`(mtime + content 双比对) |
| 权限门 → 拒绝回喂自纠 | `registry.py` `_ask_permission` | CC `canUseTool` 权限系统 |
| 流式打字机 + reasoning round-trip | `mini_cc.py` chunk 累积 | DeepSeek thinking-mode 契约(reasoning_content 必须回传) |
| token 二维记账(billed vs context) | `mini_cc.py` `_finish` | 揭示无 prompt-cache 时 history 被重复计费 |
| 显式终止 TerminalReason | `mini_cc.py` `TurnTerminal` | CC `query.ts` Terminal discriminated union |
| grace call(撞顶前收尾) | `mini_cc.py` turn loop | Hermes `conversation_loop` budget grace call |
| 子 agent 委派 | `tools/task.py` | CC `AgentTool` · Hermes `delegate_tool.py` |
| 子状态隔离(ContextVar) | `state.py` | CC `forkedAgent.ts` `createSubagentContext` |
| 工具子集过滤(防递归) | `registry.py` `tools_schema(allowed=)` | Hermes `DELEGATE_BLOCKED_TOOLS` |
| 递归 depth limit | `tools/task.py` | Hermes `delegate_tool.py` `max_spawn_depth` |
| partition 并发调度 | `mini_cc.py` `_partition_tool_calls` | CC `toolOrchestration.ts` partitionToolCalls |

---

## 子 agent 设计(亮点)

`task` 工具 spawn 一个独立子 agent 执行委派任务,体现完整的 agent 系统设计:

- **三大独立性**:子有自己的对话历史(空白起步)、独立的文件读状态(ContextVar 栈式隔离)、独立的迭代预算。
- **工具子集**:子看不到 `task` 工具本身,叠加 depth 守卫防递归 spawn 失控。
- **递归 + 深度限制**:允许子 spawn 孙(层级化任务分解),`MAX_SUBAGENT_DEPTH` 守卫撞顶时返回错误,模型收到后自我纠错。
- **并发调度**:同一轮的多个 read-only 工具(含 `task`)按 partition 自动并行(ThreadPoolExecutor),写工具串行 —— 自动避开"并发权限门竞争"和"写冲突 race"。
- **权限下放**:`task` 本身不弹权限门(对照 CC `AgentTool.isReadOnly=true`),真正的副作用(子内部的 write/bash)各自弹权限确认。

---

## 故意不做(诚实边界 = 判断力)

为保持"最小可用"且不被无关复杂度拖死,以下明确不做:

- **MCP**(真协议,最重,这类玩具项目十有八九死在这里)
- **真上下文压缩 / microcompact**(1M context 窗口下当前用不到)
- **skill 系统**(SKILL.md 渐进披露)/ **TUI**(Ink 等富终端)/ **插件系统**
- **多 provider gateway · cron · kanban · profile 隔离 · 会话持久化**

这些不是"不会做",是"做了会偏离核心、且不增加对 agent 本质的理解"。

---

## 栈

Python 3.13 · DeepSeek(`openai` SDK,OpenAI 兼容协议)· `python-dotenv` · 标准库 `contextvars` / `concurrent.futures` · **无 agent 框架**
