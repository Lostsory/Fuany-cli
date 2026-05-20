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

from dataclasses import dataclass


@dataclass
class FileSeen:
    """agent 已经读过的文件的「mtime + 内容」快照。"""

    mtime: float
    content: str


READ_STATE: dict[str, FileSeen] = {}
