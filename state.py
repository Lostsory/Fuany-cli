"""Agent 运行时上下文状态。

每个 agent 的 read_state 保存文件的修改时间和文本 SHA-256 摘要，不保留正文。
write/edit 在修改时间变化时比较摘要，避免仅触碰 mtime 就误报内容变化。
调用方决定字典生命周期，ContextVar 负责让工具访问当前 agent 的字典。
"""

from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256


@dataclass
class FileSeen:
    """agent 已经读过的文件的修改时间与文本摘要。"""

    mtime: float
    content_hash: str


def hash_content(content: str) -> str:
    """对工具读写的文本计算稳定摘要，保持原来的文本比较语义。"""
    return sha256(content.encode("utf-8")).hexdigest()


# agent 入口显式绑定自己的字典，退出时通过 token 恢复上一层绑定。
_read_state_var: ContextVar[dict[str, FileSeen]] = ContextVar("read_state")


def get_read_state() -> dict[str, FileSeen]:
    """获取当前的 READ_STATE。"""
    try:
        return _read_state_var.get()
    except LookupError:
        # 首次访问时，ContextVar 未设置，触发 LookupError。
        # 初始化一个空字典并设置到 ContextVar。
        default: dict[str, FileSeen] = {}
        _read_state_var.set(default)
        return default


def set_read_state(state: dict[str, FileSeen]):
    """设置当前的 READ_STATE。"""
    return _read_state_var.set(state)


def reset_read_state(token):
    """重置当前的 READ_STATE 到 token 对应的初始值。"""
    _read_state_var.reset(token)


_depth_var: ContextVar[int] = ContextVar("depth", default=0)


def get_depth() -> int:
    """获取当前 agent 的递归深度。"""
    return _depth_var.get()


def set_depth(depth: int):
    """设置当前 agent 的递归深度,返回 token 用于 reset。"""
    return _depth_var.set(depth)


def reset_depth(token):
    """重置 depth 到 token 对应的上一层。"""
    _depth_var.reset(token)
