"""task 工具:spawn 子 agent 执行委派任务。

对照真源码:
  - Hermes delegate_tool.py:1106-1137 (新建 AIAgent + run_conversation)
  - CC AgentTool.tsx:82-138 (input schema) + runAgent.ts:248-329 (async generator)

mini-cc 简化:
  - 调 agent_answer() 实现子 agent,不新建实例(mini-cc 没"agent 实例"概念,函数就是 agent)
  - read_state 独立(ContextVar 栈式隔离)
  - quiet=True 静默子的中间过程
  - 子用 SUBAGENT_SYSTEM(对照 Hermes _build_child_system_prompt)
"""

from config import DEFAULT_MAX_TURNS_SUBAGENT, SUBAGENT_SYSTEM
from registry import register


@register(
    "task",
    "委派一个子 agent 执行明确的子任务。用于:深度调研、多文件分析、独立子流程。"
    "子 agent 有自己的对话历史,只返回最终回答给你。",
    {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "任务简短标题(3-5 字),仅显示用",
            },
            "prompt": {
                "type": "string",
                "description": "委派给子 agent 的具体任务描述(完整 prompt)",
            },
        },
        "required": ["description", "prompt"],
    },
    read_only=False,
)
def task(description: str, prompt: str) -> str:
    """spawn 子 agent 执行委派任务,返回 final content。

    子拿空白 messages + 新 read_state(ContextVar 栈式隔离)
    + quiet 静默 + SUBAGENT_SYSTEM 身份 + DEFAULT_MAX_TURNS_SUBAGENT 上限。
    """
    from mini_cc import agent_answer

    print(f"\n  🛠️  spawn 子 agent: {description}")

    sub_msgs: list = [
        {"role": "system", "content": SUBAGENT_SYSTEM},
    ]

    terminal = agent_answer(
        prompt,
        sub_msgs,
        max_turns=DEFAULT_MAX_TURNS_SUBAGENT,
        read_state={},
        quiet=True,
    )

    print(f"  ✓ 子 agent 完成: {description}")

    return terminal.content or "（子 agent 无回答）"
