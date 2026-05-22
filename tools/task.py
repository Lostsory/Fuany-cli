"""task 工具:spawn 子 agent 执行委派任务。

对照真源码:
  - Hermes delegate_tool.py:1106-1137 (新建 AIAgent + run_conversation)
  - CC AgentTool.tsx:82-138 (input schema) + runAgent.ts:248-329 (async generator)

mini-cc 简化:
  - 调 agent_answer() 实现子 agent,不新建实例(mini-cc 没"agent 实例"概念,函数就是 agent)
  - read_state 独立(ContextVar 栈式隔离)
  - quiet=True 静默子的中间过程
  - 子用 SUBAGENT_SYSTEM(对照 Hermes _build_child_system_prompt)
  - 子 agent 不允许调用 SUBAGENT_BLOCKED 中的工具
"""

from config import (
    DEFAULT_MAX_TURNS_SUBAGENT,
    MAX_SUBAGENT_DEPTH,
    SUBAGENT_BLOCKED,
    SUBAGENT_SYSTEM,
)
from registry import REGISTRY, register
from state import get_depth


# read_only=True 对照 CC AgentTool.tsx:1264 isReadOnly()——
# task 本身不直接改东西,权限检查"下放给子 agent 内部的工具"
# (子的 write/edit/bash 各自弹权限门)。这让:
#   1. 委派动作本身不弹权限门(用户批准的是子的实际操作)
#   2. task 归入"并发安全"批,多个 task 可并行 spawn
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
    read_only=True,
)
def task(description: str, prompt: str) -> str:
    """spawn 子 agent 执行委派任务,返回 final content。

    子拿空白 messages + 新 read_state(ContextVar 栈式隔离)
    + quiet 静默 + SUBAGENT_SYSTEM 身份 + DEFAULT_MAX_TURNS_SUBAGENT 上限。
    """
    from mini_cc import agent_answer

    cur_depth = get_depth()
    child_depth = cur_depth + 1

    if child_depth > MAX_SUBAGENT_DEPTH:
        return (
            f"错误: 已达最大递归深度 {MAX_SUBAGENT_DEPTH}(当前 depth={cur_depth}),"
            f"不能再 spawn 子 agent。请基于已有信息完成任务,不要再调 task。"
        )

    print(f"\n  🛠️  spawn 子 agent (depth={child_depth}): {description}")

    # 子的工具集 = 全集 - blocked(对照 Hermes _strip_blocked_tools 减去 DELEGATE_BLOCKED_TOOLS)
    child_allowed: set[str] = set(REGISTRY.keys()) - SUBAGENT_BLOCKED
    sub_msgs: list = [
        {"role": "system", "content": SUBAGENT_SYSTEM},
    ]

    terminal = agent_answer(
        prompt,
        sub_msgs,
        max_turns=DEFAULT_MAX_TURNS_SUBAGENT,
        read_state={},
        quiet=True,
        allowed=child_allowed,
        depth=child_depth,
    )

    print(f"  ✓ 子 agent (depth={child_depth}) 完成: {description}")

    return terminal.content or "（子 agent 无回答）"
