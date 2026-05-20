"""工具注册表：一个工具的真相（name + description + JSON schema + handler）
收在一处声明，发给 LLM 的 tools 载荷和运行时派发都从这里【派生】，不手动同步两份。

对照真源码：
  - Claude Code  src/Tool.ts:783  buildTool(def) —— 一个对象装全部
  - Hermes       tools/registry.py:234  registry.register(name, schema, handler, ...)
                 + tools/__init__ import 即注册（「发现」），toolset 决定「暴露」

本文件提供「发现/声明」与「派生」；「暴露」的子集过滤是 subagent（D6）的事，
这里只留 allowed 参数的缝，D1 不实现过滤。
"""

from dataclasses import dataclass
from typing import Callable

from log import _log


@dataclass(frozen=True)
class Tool:
    """一个工具的完整真相，不可变。

    name        : LLM 在 tool_call 里写的名字，也是派发 key
    description : 给 LLM 看的说明（决定它会不会、怎么调）
    parameters  : JSON Schema 的 parameters 块（{"type":"object","properties":...}）
    handler     : 真正干活的函数，**args 解包调用，返回字符串
    """

    name: str
    description: str
    parameters: dict
    handler: Callable[..., str]


# 模块级单例。import 本模块即存在；各工具模块顶层 @register 往这里灌。
REGISTRY: dict[str, Tool] = {}


def register(name: str, description: str, parameters: dict):
    """装饰器：把被装饰函数构造成 Tool 塞进 REGISTRY，原函数原样返回。

    用法：
        @register("grep", "基于 ripgrep 的搜索...", {"type":"object", ...})
        def grep(pattern, glob="*.md"): ...
    """

    def deco(fn: Callable[..., str]) -> Callable[..., str]:
        # 没有插件热重载，让错误在import阶段就抛出
        if name in REGISTRY:
            raise ValueError(f"Tool {name} is already registered")
        REGISTRY[name] = Tool(name, description, parameters, fn)
        return fn

    return deco


def tools_schema(allowed: set[str] | None = None) -> list[dict]:
    """从 REGISTRY 派生 OpenAI chat.completions 的 tools= 载荷。

    schema 从注册表派生，不手动维护第二份独立列表 —— 两份必漂移。

    allowed=None → 全部暴露（D1 行为）；allowed=集合 → 只暴露子集
    （D6 subagent 用，D1 先不实现过滤，留这个参数别堵死）。
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
    ]


def call_tool(name: str, args: dict) -> str:
    """按名字派发到 handler。LLM 可能塞 handler 不收的参数，不让它崩程序，
    把错误当字符串返回 → agent 循环把它当 tool_result 回喂、自我纠错。
    （这个防御性派发是 D3 权限门「拒绝→回喂」自我纠错的同款种子，别删。）

    """

    if name not in REGISTRY:
        ans = f"未知工具: {name}"
        _log(name, args, ans, False)
        return ans

    try:
        ans = REGISTRY[name].handler(**args)
    except TypeError as e:
        ans = f"工具 {name} 参数错误: {e}。请检查参数名后重试。"
        _log(name, args, ans, False)
        return ans

    _log(name, args, ans, True)
    return ans
