"""mini-claude-code 入口：function-calling agent 循环。

裸写核心循环，不用任何 agent 框架。一个回合 = 反复
  调模型 → 有 tool_calls 就执行并把结果回喂 → 没有就结束。

对照 Claude Code：src/query.ts queryLoop —— 单个 while 重赋值 State，
主出口是"模型不再要求调工具 = completed"。本文件是它的最小忠实版。

工具不在这里硬编码：`import tools` 触发自动注册，循环只从注册表
派生 schema（tools_schema）和派发（call_tool）。
"""

import json
import readline  # noqa: F401  # 副作用导入：给 input() 接上 line-editing 后端，让中文/方向键/历史都能用
from typing import cast

from openai.types.chat import (
    ChatCompletionMessageFunctionToolCallParam,
    ChatCompletionMessageParam,
)

import tools  # noqa: F401  # import 即触发 tools/ 下所有 @register
from llm import build_llm
from registry import call_tool, tools_schema

MAX_STEPS = 8  # 防失控上限。D5 会用 token 预算取代这个魔法数，D1 先留着

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


def agent_answer(question: str, messages: list[ChatCompletionMessageParam]) -> str:
    """agent 循环：调模型 ↔ 跑工具，多轮直到模型不再要工具。"""
    llm = build_llm()  # 需支持 function calling
    messages.append({"role": "user", "content": question})

    # 本轮 token 记账,两套数都要:
    #   billed_*  = 跨 step 累加,**= 这一轮被计费的总额**。
    #               注意 multi-step 时每个 step 的 prompt 都全额包含 history,
    #               所以累加值会远大于上下文长度 —— 这不是 bug,是 API
    #               按"每次请求全额 prompt"计费的真相(无 prompt cache 时)。
    #   last_prompt = 最后一次 step 的 prompt_tokens
    #               **= 本轮结束时对话历史的真实长度(上下文窗口占用)**。
    # 两个数同时打,把"计费账"和"上下文账"分清。
    billed_prompt_tokens = 0
    billed_completion_tokens = 0
    last_prompt_tokens = 0

    for step in range(MAX_STEPS):
        stream = llm.client.chat.completions.create(
            model=llm.model,
            messages=messages,
            tools=tools_schema(),
            stream=True,
            stream_options={"include_usage": True},
        )

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_accum: dict[int, dict[str, str]] = {}
        seen_reasoning = False  # 用于在 reasoning → content 转场时插一次换行+💡 标识

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
            ctx_pct = last_prompt_tokens / llm.context_window * 100
            ctx_max = (
                f"{llm.context_window // 1_000_000}M"
                if llm.context_window >= 1_000_000
                else f"{llm.context_window // 1000}k"
            )
            print(
                f"\n\033[90m[billed: in={billed_prompt_tokens} "
                f"out={billed_completion_tokens} "
                f"total={billed_prompt_tokens + billed_completion_tokens} "
                f"| context: {last_prompt_tokens}/{ctx_max} ({ctx_pct:.1f}%)]\033[0m"
            )
            return full_content or "（无回答）"

        # 把 LLM "要调工具"那条消息存回（响应 delta 拼成入参格式）
        assistant_msg: dict = {
            "role": "assistant",
            "content": full_content or None,
            "tool_calls": tool_calls,
        }
        if full_reasoning:
            assistant_msg["reasoning_content"] = full_reasoning
        messages.append(assistant_msg)

        # 流式 reasoning/content 没有自带换行，[step N] 直接贴上来视觉乱。
        # 这里(仅在有工具调用时)补一次换行；final answer 那条路径交给 main 处理。
        print()

        for tc in tool_calls:
            if tc["type"] != "function":
                continue
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            print(f"  [step {step}] {name}({args})")

            result = call_tool(name, args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                }
            )

    print(
        f"\n\033[90m[billed: in={billed_prompt_tokens} "
        f"out={billed_completion_tokens} "
        f"total={billed_prompt_tokens + billed_completion_tokens} "
        f"| context: {last_prompt_tokens}]\033[0m"
    )
    return "（达到最大步数仍未给出答案）"


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
