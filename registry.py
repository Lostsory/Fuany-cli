"""工具注册表：一个工具的真相（name + description + JSON schema + handler）
收在一处声明，发给 LLM 的 tools 载荷和运行时派发都从这里【派生】，不手动同步两份。

对照真源码：
  - Claude Code  src/Tool.ts:783  buildTool(def) —— 一个对象装全部
  - Hermes       tools/registry.py:234  registry.register(name, schema, handler, ...)
                 + tools/__init__ import 即注册（「发现」），toolset 决定「暴露」

本文件提供「发现/声明」与「派生」；「暴露」的子集过滤是 subagent（D6）的事，
这里只留 allowed 参数的缝，D1 不实现过滤。
"""

import sys
from dataclasses import dataclass
from typing import Callable

from openai.types.chat import ChatCompletionToolUnionParam

from config import AUTO_ALLOW
from log import log


@dataclass(frozen=True)
class Tool:
    """一个工具的完整真相，不可变。

    name        : LLM 在 tool_call 里写的名字，也是派发 key
    description : 给 LLM 看的说明（决定它会不会、怎么调）
    parameters  : JSON Schema 的 parameters 块（{"type":"object","properties":...}）
    handler     : 真正干活的函数，**args 解包调用，返回字符串
    read_only   : 是否只读工具（不修改状态，只读取）
    """

    name: str
    description: str
    parameters: dict[str, object]
    handler: Callable[..., str]
    read_only: bool = False


# 模块级单例。import 本模块即存在；各工具模块顶层 @register 往这里灌。
REGISTRY: dict[str, Tool] = {}


def register(
    name: str,
    description: str,
    parameters: dict[str, object],
    *,
    read_only: bool = False,
):
    """装饰器：把被装饰函数构造成 Tool 塞进 REGISTRY，原函数原样返回。

    用法：
        @register("grep", "基于 ripgrep 的搜索...", {"type":"object", ...})
        def grep(pattern, glob="*.md"): ...
    """

    def deco(fn: Callable[..., str]) -> Callable[..., str]:
        # 没有插件热重载，让错误在import阶段就抛出
        if name in REGISTRY:
            raise ValueError(f"Tool {name} is already registered")
        REGISTRY[name] = Tool(name, description, parameters, fn, read_only)
        return fn

    return deco


def tools_schema(allowed: set[str] | None = None) -> list[ChatCompletionToolUnionParam]:
    """从 REGISTRY 派生 OpenAI chat.completions 的 tools= 载荷。

    schema 从注册表派生，不手动维护第二份独立列表 —— 两份必漂移。

    allowed=None → 全部暴露（D1 行为）；allowed=集合 → 只暴露子集
    """

    return [
        {
            "type": "function",
            "function": {
                "name": v.name,
                "description": v.description,
                "parameters": v.parameters,
            },
        }
        for v in REGISTRY.values()
        if allowed is None or v.name in allowed
    ]


def _ask_permission(name: str, args: dict) -> bool:
    """side-effect 工具执行前问用户。返回 True = 允许;False = 拒绝。

    MINI_CC_AUTO_ALLOW 环境变量绕过(非交互测试用,默认不设)。

    UX 关键:进 input() 前先 flush stdin —— 否则一轮里多个 parallel
    tool_calls 顺序问的时候,用户在 prompt 出现前误按的 y 会被 tty
    buffer 住,下一个 input() 直接消费,造成"按 y 没反应"的同步错位。
    清空后,必须在看到 ⚠️ 之后按的 y 才算数。
    """
    if AUTO_ALLOW:
        return True

    if sys.stdin.isatty():
        import termios

        termios.tcflush(sys.stdin, termios.TCIFLUSH)

    print(f"\n⚠️  agent 想执行: {name}({args})")
    return input("允许? [y/N] ").strip().lower() == "y"


def call_tool(name: str, args: dict) -> str:
    """按名字派发到 handler。LLM 可能塞 handler 不收的参数，不让它崩程序，
    把错误当字符串返回 → agent 循环把它当 tool_result 回喂、自我纠错。
    （这个防御性派发是 D3 权限门「拒绝→回喂」自我纠错的同款种子，别删。）

    """

    if name not in REGISTRY:
        ans = f"未知工具: {name}"
        log(name, args=args, result=ans, dispatched=False)
        return ans

    tool = REGISTRY[name]

    if not tool.read_only and not _ask_permission(name, args):
        ans = f"用户拒绝执行: {name}({args})"
        log(name, args=args, result=ans, dispatched=False)
        return ans

    try:
        ans = tool.handler(**args)
    except TypeError as e:
        ans = f"工具 {name} 参数错误: {e}。请检查参数名后重试。"
        log(name, args=args, result=ans, dispatched=False)
        return ans

    log(name, args=args, result=ans, dispatched=True)
    return ans
