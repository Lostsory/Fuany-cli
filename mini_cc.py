"""mini-claude-code 入口：function-calling agent 循环。

裸写核心循环，不用任何 agent 框架。一个回合 = 反复
  调模型 → 有 tool_calls 就执行并把结果回喂 → 没有就结束。

对照 Claude Code：src/query.ts queryLoop —— 单个 while 重赋值 State，
主出口是"模型不再要求调工具 = completed"。本文件是它的最小忠实版。

工具不在这里硬编码：`import tools` 触发自动注册，循环只从注册表
派生 schema（tools_schema）和派发（call_tool）。
"""

import json
from typing import cast

from openai.types.chat import ChatCompletionMessageParam

import tools  # noqa: F401  # import 即触发 tools/ 下所有 @register
from llm import build_llm
from registry import call_tool, tools_schema

MAX_STEPS = 8  # 防失控上限。D5 会用 token 预算取代这个魔法数，D1 先留着

SYSTEM = (
    "你是文档/代码检索助手，可用 grep 和 read_file 两个工具。"
    "策略：先用 grep 写正则找相关文件（pattern 保留问题核心词，可用 | 加同义说法）；"
    "拿到路径后用 read_file 读整篇；不够就再 grep 换 pattern 或读别的文件。"
    "只根据读到的资料回答，注明依据哪个文件；资料里没有就直说不知道，不要编造。"
)


def agent_answer(question: str) -> str:
    """agent 循环：调模型 ↔ 跑工具，多轮直到模型不再要工具。"""
    llm = build_llm()  # 需支持 function calling
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]

    for step in range(MAX_STEPS):
        resp = llm.client.chat.completions.create(
            model=llm.model,
            messages=messages,
            tools=tools_schema(),  # ← 用 tools_schema()
        )
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls

        if not tool_calls:
            return msg.content or "（无回答）"

        # 把 LLM "要调工具"那条消息存回（cast 解决响应/入参类型摩擦）
        messages.append(cast(ChatCompletionMessageParam, msg))

        for tc in tool_calls:
            if tc.type != "function":
                continue
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            print(f"  [step {step}] {name}({args})")

            # TODO(D1) ②：派发交给注册表统一处理（未知工具 / 参数错误
            #          都由 call_tool 转成可回喂字符串，不在这里 if/try）
            result = call_tool(name, args)  # ← 用 call_tool(name, args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                }
            )

    return "（达到最大步数仍未给出答案）"


def main():
    # demo：让它检索自己的代码库（它是个 coding agent，跑哪搜哪）。
    # 想换问题随便改，判据看的是"经注册表跑通"，不是具体问哪句。
    for q in [
        "在当前目录建一个 hello.txt，内容写 '你好 mini-cc'",  # write
        "把刚刚建的 hello.txt 里的 '你好' 改成 'hello'",  # edit
        "用 glob 找一下当前目录下所有 .py 和 .txt 文件",  # glob
        "用 bash 跑 `ls -la`，并在 description 里写明你为什么跑这个",  # bash + 试 description 是否被记录
    ]:
        print(f"\n❓ {q}")
        print(f"💡 {agent_answer(q)}")


if __name__ == "__main__":
    main()
