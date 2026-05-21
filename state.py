"""Agent 运行时共享状态。

READ_STATE: 每个被读过的文件的「mtime + 内容」快照。write/edit 前比对，
不一致 → 拒绝 + 喂回让 agent 重读再改。

对照 Claude Code: src/Tool.ts:181 `readFileState: FileStateCache`
（CC 是 ToolUseContext 字段，per-run 独立；我们暂用全局单例，
D6 子 agent 时需改为 per-context，是已知技术债）。

双比对(mtime + content fallback) 的理由 (CC 源码 FileWriteTool.ts:283-292)：
Windows 上 cloud sync / 杀毒软件会触碰 mtime 但不改内容，纯 mtime 比对会
false positive。我们 macOS 用不到，但保留这个工业级做法。
"""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class FileSeen:
    """agent 已经读过的文件的「mtime + 内容」快照。"""

    mtime: float
    content: str


# 把 READ_STATE 从全局 dict → ContextVar。
# 对照 CC forkedAgent.ts:376-417 createSubagentContext 的 readFileState 隔离:
# CC 用深拷贝传 context 对象;Python 用 ContextVar 自动栈式隔离,nested set/reset 安全。
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
