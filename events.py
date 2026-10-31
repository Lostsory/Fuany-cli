"""Agent 与 Web 会话的事件契约，保留可直接 JSON 序列化的字典结构。

每种事件用 type 字段区分，其余字段均为必填；消费者判断 type 后，
类型检查器便能确定可访问的字段。TypedDict 只提供静态类型检查，
不会在运行时校验传入数据。

mini_cc.py 通过回调产生 AgentEvent；server.py 补充会话和授权事件，
保存到会话历史并通过 SSE 发送给前端。前端对应定义见 frontend/src/events.ts。
"""

from typing import Callable, Literal, TypedDict


# 正常完成、迭代预算耗尽、提示超出模型上下文窗口。
type TerminalReason = Literal["completed", "max_turns", "prompt_too_long"]


class TextDeltaEvent(TypedDict):
    """模型新生成的一段回答文本；前端按接收顺序追加，而非替换全文。"""

    type: Literal["delta"]
    content: str  # 本次流式增量，不包含推理文本。


class ToolStartEvent(TypedDict):
    """准备派发工具调用，此时工具尚未返回，也可能在等待用户授权。"""

    type: Literal["tool_start"]
    id: str  # 模型生成的 tool_call ID，用于关联对应的 tool_end。
    name: str  # 注册表中的工具名。
    args: dict[str, object]  # 从模型工具调用中解析出的参数。


class ToolEndEvent(TypedDict):
    """工具调用已返回；返回不代表成功，也可能是拒绝执行或参数错误。"""

    type: Literal["tool_end"]
    id: str  # 与对应 tool_start 使用同一个 tool_call ID。
    name: str
    result: str  # 展示给用户并回喂模型的工具返回文本。


# 核心循环只产生文本和工具事件，不依赖 Web 的会话与授权流程。
type AgentEvent = TextDeltaEvent | ToolStartEvent | ToolEndEvent
# 同步通知消费者；不设置回调时，CLI 仍按原有方式输出。
type EventHandler = Callable[[AgentEvent], None]


class UserEvent(TypedDict):
    """后端接受的一条用户消息，标记会话历史中新一轮对话的开始。"""

    type: Literal["user"]
    content: str


class ApprovalEvent(TypedDict):
    """工具执行前请求网页授权；前端展示工具名与参数，供用户决定。"""

    type: Literal["approval"]
    id: str  # 后端生成的授权请求 ID，与模型的 tool_call ID 不同。
    name: str
    args: dict[str, object]


class ApprovalResolvedEvent(TypedDict):
    """授权请求已结束，前端应关闭对应弹窗。"""

    type: Literal["approval_resolved"]
    id: str  # 对应 approval 事件的授权请求 ID。
    allowed: bool  # True 为用户允许；拒绝、超时或断开连接时为 False。


class DoneEvent(TypedDict):
    """Agent 本轮运行已返回终止结果；异常退出使用 ErrorEvent。

    字段对应 mini_cc.TurnTerminal。前端通常已有 delta 累积的回答，
    content 用于无增量回答时的兜底，或展示预算耗尽、上下文超限提示。
    """

    type: Literal["done"]
    reason: TerminalReason
    content: str  # 最终回答或终止提示。
    turn_count: int  # 仅 max_turns 时有意义，为预算耗尽时已运行的迭代数。
    limit_tokens: int | None  # 上下文超限时解析出的 token 上限，未知则为 None。
    grace_used: bool  # 是否已在最后一次迭代前注入收尾提醒。


class ErrorEvent(TypedDict):
    """本轮运行异常或连接中断的用户提示，不暴露内部异常详情。"""

    type: Literal["error"]
    content: str


# Web 会话保存和传输的完整事件集合，包含核心 Agent 事件及 Web 扩展事件。
type SessionEvent = (
    AgentEvent
    | UserEvent
    | ApprovalEvent
    | ApprovalResolvedEvent
    | DoneEvent
    | ErrorEvent
)
