# Fuany CLI

原 mini-claude-code，提供 `fuany` 命令行和本地 Web 界面。

一个**不依赖任何 agent 框架**(LangChain / LlamaIndex 等)、纯 Python 裸写的最小可用 coding agent。核心循环自己拥有,逐特性对照 [Claude Code](https://claude.com/claude-code) 与 Hermes(Nous Research)真实源码实现,并**诚实标注哪些故意没做**。

> 不是克隆,是"读真源码 → 理解每个特性为什么这么设计 → 用最小代码忠实复刻 → 想清楚哪些该简化、哪些该砍"。每个特性都能讲清它在 CC/Hermes 源码的哪里、我为什么这么简化。

默认使用 DeepSeek（OpenAI 兼容协议）。可在 `llm.py` 的 `PROVIDER` 切换到已配置的 Ollama；新增 provider 还需补充对应接入配置。

---

## 为什么裸写、不用框架

读 Claude Code 与 Hermes 源码后确认:**二者都不用 LangChain**。Agent 循环就是产品本体 —— "调模型 → 有工具调用就执行并回喂 → 没有就结束"这个 while 循环,框架抽象只会遮蔽它且随版本漂移。本项目沿用同一取舍:**核心循环自己拥有,看得见、改得动**。

---

## 快速开始

```bash
# 1. 安装依赖（Python 3.13+，使用 uv）
uv sync

# 2. 首次配置：复制模板，在 .env 中填写真实 API key
cp .env.example .env

# 3. 启动交互式 REPL
uv run fuany
# 也可直接运行：uv run python mini_cc.py
```

进入后像 `claude` 一样多轮对话。`exit` / `quit` / Ctrl-D 退出。

环境变量（集中在 `config.py` 读取；修改后需重启进程）：

| 变量 | 默认 | 作用 |
|---|---|---|
| `DEEPSEEK_API_KEY` | — | DeepSeek 凭证(必填) |
| `MINI_CC_MAX_TURNS` | 90 | 父 agent 单轮最大迭代数 |
| `MINI_CC_MAX_TURNS_SUBAGENT` | 50 | 子 agent 最大迭代数 |
| `MINI_CC_MAX_SUBAGENT_DEPTH` | 2 | 子 agent 最大递归深度 |
| `MINI_CC_MAX_PARALLEL` | 10 | 每个并行工具批次的最大线程数，不是跨所有 agent 的全局上限 |
| `MINI_CC_BRAVE_SEARCH_API_KEY` | 未设置 | Brave 搜索凭证；未配置时 `web_search` 返回提示 |
| `MINI_CC_SKILL_DIR` | `skills` | 本地 skill 扫描目录 |
| `MINI_CC_SHOW_THINKING` | false | 是否在 CLI 显示 reasoning，不影响生成和历史回传 |
| `MINI_CC_AUTO_ALLOW` | false | CLI 测试时跳过权限确认；设为 `1` / `true` / `yes` 开启。Web 授权处理器优先，仍逐次确认 |

---

## Web 界面

在现有 CLI 之外，提供 React + TypeScript + Vite + 原生 CSS 前端与 FastAPI 后端，复用同一个 Agent 循环及工具系统。支持流式聊天、多轮会话、Markdown、工具执行记录，以及网页工具授权。

```bash
# 在项目根目录安装后端依赖
uv sync

# 安装并构建前端
cd frontend
npm ci
npm run build
cd ..

# 启动前后端服务
uv run fuany-web
```

打开 **http://127.0.0.1:8000**。模型凭证继续使用根目录 `.env` 中的 `DEEPSEEK_API_KEY`。

开发时分别运行 `uv run uvicorn server:app --host 127.0.0.1 --port 8000 --reload` 和 `cd frontend && npm run dev`，然后访问 http://127.0.0.1:5173。

会话保存在后端内存中，刷新网页后可恢复，重启后端后清空；请使用单个服务进程。网页中的文件操作基于后端启动目录执行，写文件和 shell 命令需逐次授权。关闭网页会中断后续生成，已经完成的工具操作不会撤销。

验证：`uv run pytest -q`、`uv run ruff check server.py mini_cc.py registry.py tests`、`cd frontend && npm run build && npm run lint`。更多说明见 [frontend/README.md](frontend/README.md)。

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
   ├─ grace call(最后一次迭代提醒收尾，并设置 tool_choice="none")
   └─ 工具派发
         │
         ▼
   registry.call_tool()  ── 权限门 + 未知工具/参数错误处理 + 派发
         │
         ▼
   tools/  ── read_file / grep / glob / write / edit / bash
             tool_search / task / load_skill / web_search / web_fetch
             （文件修改检查在 write/edit 内执行）
```

| 模块 | 职责 |
|---|---|
| `mini_cc.py` | 入口 + 核心 agent 循环 + 流式 + 终止判定 + 并发调度 |
| `registry.py` | 工具注册表(一处声明,schema 与派发都从此派生)+ 权限门 |
| `config.py` | 所有 env 读取的单一入口(fail-loud + 类型化常量) |
| `llm.py` | LLM 构造(client + model + context_window 捆绑,一处切 provider) |
| `state.py` | per-agent 文件读取记录（mtime + SHA-256 摘要），通过 ContextVar 访问 |
| `tools/` | 工具实现,`import tools` 即触发自动注册 |
| `server.py` | FastAPI 会话、SSE 流式事件、网页授权和前端静态文件服务 |
| `events.py` | Python 端事件类型；前端对应 `frontend/src/events.ts` |
| `frontend/` | React + TypeScript + Vite 本地 Web 界面 |
| `tests/` | agent 事件、Web API、文件摘要守卫与状态清理测试 |

---

## 特性 × 源码对照(receipts)

每个特性都对照真源码实现,不凭想象:

| 特性 | 实现 | 对照源码 |
|---|---|---|
| 工具注册表(声明=派生) | `registry.py` `@register` | CC `Tool.ts` · Hermes `tools/registry.py`(注册≠暴露) |
| mod-time 守卫(防外部偷改) | `tools/files.py` write/edit：mtime + SHA-256 摘要 | 参考 CC `FileWriteTool.ts` 的 mtime + 内容双比对；本项目用摘要替代正文存储 |
| 权限门 → 拒绝回喂自纠 | `registry.py` `_ask_permission` | CC `canUseTool` 权限系统 |
| 流式打字机 + reasoning round-trip | `mini_cc.py` chunk 累积 | DeepSeek thinking-mode 契约(reasoning_content 必须回传) |
| token 二维记账(billed vs context) | `mini_cc.py` `_finish` | 揭示无 prompt-cache 时 history 被重复计费 |
| 显式终止 TerminalReason | `mini_cc.py` `TurnTerminal` | CC `query.ts` Terminal discriminated union |
| grace call(撞顶前收尾) | `mini_cc.py` turn loop | Hermes `conversation_loop` budget grace call |
| 子 agent 委派 | `tools/task.py` | CC `AgentTool` · Hermes `delegate_tool.py` |
| 子状态隔离(ContextVar) | `state.py` | CC `forkedAgent.ts` `createSubagentContext` |
| 工具 schema 子集过滤 | `registry.py` `visible_tool_names` / `tools_schema(allowed=)`；默认子 agent 禁用集合为空 | 参考 Hermes `DELEGATE_BLOCKED_TOOLS`；递归由 depth 守卫控制 |
| 递归 depth limit | `tools/task.py` | Hermes `delegate_tool.py` `max_spawn_depth` |
| partition 并发调度 | `mini_cc.py` `_partition_tool_calls` | CC `toolOrchestration.ts` partitionToolCalls |
| skill 渐进披露 | `skills.py` + `tools/skill.py` | CC `loadSkillsDir.ts` · `SkillTool.ts`(listing 进 prompt + 全文按需 load) |
| web_search | `tools/web.py` | Brave API(CC WebSearch 是 Anthropic server-tool,DeepSeek 走客户端调 API) |
| web_fetch（抓取、提炼、字符 offset 分页） | `tools/web.py` | 参考 CC `WebFetchTool`；本项目提供 offset 继续读取 |

---

工具采用渐进暴露：`read_file`、`grep`、`glob`、`write`、`edit`、`bash`、`load_skill`、`tool_search` 默认可见；`task`、`web_search`、`web_fetch` 需先经 `tool_search` 发现，下一次模型请求才加载完整 schema。已发现工具只保留在本次 `agent_answer()` 调用中。schema 过滤不是执行沙箱，`call_tool()` 目前不接收 `allowed` 做二次校验。

`cache.py` 已提供 TTL + LRU 字符串缓存，`web_fetch` 也会查询它，但当前抓取成功后未调用缓存写入，因此正常调用不会复用抓取结果；翻页会重新请求网页。这里不将缓存复用列为已实现能力。

## 子 agent 设计(亮点)

`task` 工具 spawn 一个独立子 agent 执行委派任务,体现完整的 agent 系统设计:

- **三大独立性**:子有自己的对话历史(空白起步)、独立的文件读状态(ContextVar 栈式隔离)、独立的迭代预算。
- **文件记录与内存**：`read_state` 按路径保存修改时间和文本的 SHA-256 摘要，不保留文件正文。重复读取同一路径会覆盖记录；暂不设置 LRU 或数量上限，读取不同路径仍会增加内存占用。写入或编辑前，若修改时间变化，再比较摘要；内容变化则要求重新读取，只有时间变化则允许继续。
- **状态生命周期**：`agent_answer()` 在 `finally` 中恢复上一层 read_state 与 depth 绑定，并在子 agent（`depth > 0`）正常结束或异常退出时清空自己的记录。CLI 默认每轮创建新字典；Web 主 agent 复用会话字典，供后续轮次使用。此优化只减少 read_state 的正文存储，不减少消息历史中的工具返回文本。
- **工具范围**：子 agent 的候选工具为注册表减去 `SUBAGENT_BLOCKED`，当前该集合为空。子 agent 同样先通过 `tool_search` 发现 `task` 等 deferred 工具，再进行调用。
- **递归 + 深度限制**:允许子 spawn 孙(层级化任务分解),`MAX_SUBAGENT_DEPTH` 守卫撞顶时返回错误,模型收到后自我纠错。
- **并发调度**：单个 agent 内，连续的 read-only 工具（含 `task`）按批次使用 ThreadPoolExecutor 并行，非只读工具串行。线程提交时用 `copy_context()` 传播上下文。不同子 agent 仍可能同时写同一文件；当前没有跨 agent 的文件锁，文件修改检查也不是原子操作。
- **权限下放**:`task` 本身不弹权限门(对照 CC `AgentTool.isReadOnly=true`),真正的副作用(子内部的 write/bash)各自弹权限确认。

---

## 故意不做(诚实边界 = 判断力)

为保持"最小可用"且不被无关复杂度拖死,以下明确不做:

- **MCP**(真协议,最重,这类玩具项目十有八九死在这里)
- **上下文压缩 / microcompact**：当前未实现；上下文超限时返回终止结果，不自动压缩或续跑。窗口大小以 `llm.py` 的 provider 配置为准。
- **skill 自改进(Hermes Curator)** —— agent 给自己写 skill + 后台合并;体量是 skill 本身 5-10 倍,留作独立项目
- **TUI**(Ink 等富终端)/ **插件系统**
- **多 provider gateway · cron · kanban · profile 隔离 · 会话磁盘持久化（Web 会话目前仅存内存）**

> 注:skill **渐进披露**已实现(见上方特性表);不做的是 Hermes 式 **Curator 自改进**(那是另一个量级)。

这些不是"不会做",是"做了会偏离核心、且不增加对 agent 本质的理解"。

---

## 栈

Python 3.13+ · DeepSeek / Ollama（`openai` SDK）· FastAPI / Uvicorn · React / TypeScript / Vite · `httpx` / `markdownify` / `python-dotenv` · 标准库 `contextvars` / `concurrent.futures` · **无 agent 框架**
