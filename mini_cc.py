"""mini-claude-code 入口：function-calling agent 循环。

裸写核心循环，不用任何 agent 框架。一个回合 = 反复
  调模型 → 有 tool_calls 就执行并把结果回喂 → 没有就结束。

对照 Claude Code：src/query.ts queryLoop —— 单个 while 重赋值 State，
主出口是"模型不再要求调工具 = completed"。本文件是它的最小忠实版。

工具不在这里硬编码：`import tools` 触发自动注册，循环只从注册表
派生 schema（tools_schema）和派发（call_tool）。
"""

import json
import re
import readline  # noqa: F401  # 副作用导入：给 input() 接上 line-editing 后端，让中文/方向键/历史都能用
from dataclasses import dataclass
from typing import Literal, cast

import openai
from openai.types.chat import (
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
)

import tools  # noqa: F401  # import 即触发 tools/ 下所有 @register
from llm import build_llm
from registry import call_tool, tools_schema


@dataclass(frozen=True)
class TurnTerminal:
    """一个 turn 结束的真相，不可变。

    对照 CC query.ts L1175-1711 的 Terminal discriminated union
    + Hermes error_classifier.py:70 ClassifiedError dataclass。

    reason       : 三种终止原因之一,主辨别字段
    content      : 给 main 看的最终文案,几乎总有
    turn_count   : 仅 max_turns 时有意义,= 撞顶时已跑的 turn 数
    limit_tokens : 仅 prompt_too_long 时有意义,从错误 message 解出来的 context 上限
    """

    reason: Literal["completed", "max_turns", "prompt_too_long"]
    content: str = ""
    turn_count: int = 0
    limit_tokens: int | None = None


# 防失控逃生闸 = mini-cc 版的 CC `maxTurns`(query.ts L1705) / Hermes
# `IterationBudget`(agent/iteration_budget.py)。**不是"魔法数,D5 会删"**
# —— D5 recon 推翻了原计划:这两个范本都用迭代/turn 计数硬上限,主循环里
# 没有 token 预算 terminal。真正的"自然终止" = 模型不再要工具(见 L141)。
# 8 偏小,复杂多步任务(>4-5 个工具)会撞上,以后真要可调高,但别删。
MAX_TURNS = 8


# 对照 Hermes model_metadata.py:886-911 parse_context_limit_from_error。
# 各 provider 错误措辞不一,挑覆盖 OpenAI/DeepSeek 风格的 2-3 个 pattern。
CONTEXT_LIMIT_PATTERNS = [
    re.compile(
        r"(?:max(?:imum)?|limit)\s*(?:context\s*)?(?:length|size|window)?\s*(?:is|of|:)?\s*(\d{4,})",
        re.IGNORECASE,
    ),
    re.compile(
        r"context\s*(?:length|size|window)\s*(?:is|of|:)?\s*(\d{4,})", re.IGNORECASE
    ),
    re.compile(r"(\d{4,})\s*(?:token)?\s*(?:context|limit)", re.IGNORECASE),
    re.compile(r">\s*(\d{4,})\s*(?:max|limit|token)", re.IGNORECASE),
    re.compile(r"(\d{4,})\s*(?:max(?:imum)?)\b", re.IGNORECASE),
]

SYSTEM = (
    "你是一个交互式编码助手，帮用户做软件工程任务。"
    "使用下面的指引和可用工具(动态注册,见 tools=)来协助用户。"
    "\n\n"
    "## 工具使用\n"
    "- 简单问候直接回应，不必调工具。\n"
    "- **修改/写入文件前先读它**(read_file 看清当前内容,再 edit/write)。\n"
    "- 不要假设目录结构,先 glob/bash 看现状再动手。\n"
    "- 工具被拒绝(用户拒、未知工具、参数错)就**别重复同样调用** —— 想想原因再换方式。\n"
    "\n"
    "## 完成任务\n"
    "- 回答基于实际读到的内容;不知道就直说,不要编造。\n"
    "- 不要做超出请求范围的‘改进’(不加未要求的注释、不预制抽象)。"
)


def _finish(
    terminal: TurnTerminal,
    *,
    billed_in: int,
    billed_out: int,
    last_prompt: int,
    ctx_window: int,
) -> TurnTerminal:
    """打印 token 账单和上下文使用情况,然后返回 terminal。

    terminal: 要返回的 terminal 对象。
    billed_in: 输入 token 数量。
    billed_out: 输出 token 数量。
    last_prompt: 当前提示的 token 数量。
    ctx_window: 上下文窗口大小。
    """
    ctx_pct = last_prompt / ctx_window * 100
    ctx_max = (
        f"{ctx_window // 1_000_000}M"
        if ctx_window >= 1_000_000
        else f"{ctx_window // 1000}k"
    )
    match terminal.reason:
        case "completed":
            extra = ""
        case "max_turns":
            extra = f" 超过最大轮数 {terminal.turn_count}"
        case "prompt_too_long":
            extra = f" 提示过长 {terminal.limit_tokens}"
    print(
        f"\n\033[90m[billed: in={billed_in} "
        f"out={billed_out} "
        f"total={billed_in + billed_out} "
        f"| context: {last_prompt}/{ctx_max} ({ctx_pct:.1f}%)]"
        f" [终止: {terminal.reason}{extra}]\033[0m"
    )

    return terminal


def agent_answer(
    question: str, messages: list[ChatCompletionMessageParam]
) -> TurnTerminal:
    """agent 循环：调模型 ↔ 跑工具，多轮直到模型不再要工具。"""
    llm = build_llm()  # 需支持 function calling
    messages.append({"role": "user", "content": question})

    # 本轮 token 记账,两套数都要:
    #   billed_*  = 跨 turn 累加,**= 这一轮被计费的总额**。
    #               注意 multi-turn 时每个 turn 的 prompt 都全额包含 history,
    #               所以累加值会远大于上下文长度 —— 这不是 bug,是 API
    #               按"每次请求全额 prompt"计费的真相(无 prompt cache 时)。
    #   last_prompt = 最后一次 turn 的 prompt_tokens
    #               **= 本轮结束时对话历史的真实长度(上下文窗口占用)**。
    # 两个数同时打,把"计费账"和"上下文账"分清。
    billed_prompt_tokens = 0
    billed_completion_tokens = 0
    last_prompt_tokens = 0

    for turn in range(MAX_TURNS):
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_accum: dict[int, dict[str, str]] = {}
        seen_reasoning = False  # 用于在 reasoning → content 转场时插一次换行+💡 标识
        try:
            stream = llm.client.chat.completions.create(
                model=llm.model,
                messages=messages,
                tools=tools_schema(),
                stream=True,
                stream_options={"include_usage": True},
            )

            for chunk in stream:
                # usage 帧在流的最后,choices=[] 不是模型说的话,是计费单。
                # 先 capture 再判空,否则 chunk.choices[0] 会 IndexError。
                if chunk.usage:
                    billed_prompt_tokens += chunk.usage.prompt_tokens
                    billed_completion_tokens += chunk.usage.completion_tokens
                    last_prompt_tokens = chunk.usage.prompt_tokens
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                # DeepSeek thinking-mode 契约：reasoning_content 必须 round-trip 回 history，
                # 否则下次请求 400 ("must be passed back to the API")。
                # reasoning_content 是 DeepSeek 扩展，OpenAI SDK 的 ChoiceDelta 不声明它。
                # 用 getattr 取值，isinstance 收窄到 str：type checker 不基于 hasattr narrow，
                # isinstance 是它认的唯一 narrowing 形式。
                reasoning = getattr(delta, "reasoning_content", None)
                if isinstance(reasoning, str) and reasoning:
                    if not seen_reasoning:
                        print("🧠 ", end="", flush=True)
                        seen_reasoning = True
                    print(f"\033[90m{reasoning}\033[0m", end="", flush=True)
                    reasoning_parts.append(reasoning)

                if delta.content:
                    if seen_reasoning:
                        print("\n💡 ", end="", flush=True)
                        seen_reasoning = False
                    content_parts.append(delta.content)
                    print(delta.content, end="", flush=True)

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        slot = tool_calls_accum.setdefault(
                            tc_delta.index,
                            {
                                "id": "",
                                "name": "",
                                "args": "",
                            },
                        )
                        if tc_delta.id:
                            slot["id"] = tc_delta.id

                        if tc_delta.function:
                            if tc_delta.function.name:
                                slot["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                slot["args"] += tc_delta.function.arguments

        except openai.BadRequestError as e:
            # ⚠️ 此 except 所有分支必须 return 或 raise,不能 fall through ——
            # 否则 try 内 stream 没成功时,后续代码会拿到空 content_parts 误判为
            # "无回答"。对齐 CC "不静默 retry" 哲学(query.ts 错误处理路径都是 return/raise)。
            err = str(e)
            err_lower = err.lower()
            # 判断是否是PTL类错误
            is_ptl = any(
                s in err_lower
                for s in [
                    "context length",
                    "context_length_exceeded",
                    "too long",
                    "maximum context",
                ]
            )
            if not is_ptl:
                raise

            limit = None
            for pat in CONTEXT_LIMIT_PATTERNS:
                m = pat.search(err)
                if m:
                    limit = int(m.group(1))
                    break

            return _finish(
                TurnTerminal(
                    reason="prompt_too_long",
                    content="（上下文超出窗口）",
                    limit_tokens=limit,
                ),
                billed_in=billed_prompt_tokens,
                billed_out=billed_completion_tokens,
                last_prompt=last_prompt_tokens,
                ctx_window=llm.context_window,
            )

        full_content = "".join(content_parts)
        full_reasoning = "".join(reasoning_parts)
        tool_calls = [
            cast(
                ChatCompletionMessageFunctionToolCallParam,
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["args"],
                    },
                },
            )
            for _, tc in sorted(tool_calls_accum.items())
        ]
        if not tool_calls:
            assistant_msg: dict = {"role": "assistant", "content": full_content}
            if full_reasoning:
                assistant_msg["reasoning_content"] = full_reasoning
            messages.append(assistant_msg)
            return _finish(
                TurnTerminal(reason="completed", content=full_content or "（无回答）"),
                billed_in=billed_prompt_tokens,
                billed_out=billed_completion_tokens,
                last_prompt=last_prompt_tokens,
                ctx_window=llm.context_window,
            )

        # 把 LLM "要调工具"那条消息存回（响应 delta 拼成入参格式）
        assistant_msg: dict = {
            "role": "assistant",
            "content": full_content or None,
            "tool_calls": tool_calls,
        }
        if full_reasoning:
            assistant_msg["reasoning_content"] = full_reasoning
        messages.append(assistant_msg)

        # 流式 reasoning/content 没有自带换行，[turn N] 直接贴上来视觉乱。
        # 这里(仅在有工具调用时)补一次换行；final answer 那条路径交给 main 处理。
        print()

        for tc in tool_calls:
            if tc["type"] != "function":
                continue
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            print(f"  [turn {turn}] {name}({args})")

            result = call_tool(name, args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                }
            )

    return _finish(
        TurnTerminal(
            reason="max_turns",
            content="（达到最大步数仍未给出答案）",
            turn_count=MAX_TURNS,
        ),
        billed_in=billed_prompt_tokens,
        billed_out=billed_completion_tokens,
        last_prompt=last_prompt_tokens,
        ctx_window=llm.context_window,
    )


def main():
    messages: list[ChatCompletionMessageParam] = [
        {
            "role": "system",
            "content": SYSTEM,
        }
    ]
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return
        if not q:
            continue
        if q in ["exit", "quit"]:
            print("bye")
            return
        agent_answer(q, messages)
        print()  # 流式已经把内容逐字打过，只补个换行让下一轮提示符不贴着


if __name__ == "__main__":
    main()
