"""检索工具组：grep（调真 ripgrep）+ read_file（读整篇）。

对照 Claude Code：
  - grep      ↔ src/tools/GrepTool/GrepTool.ts  call() 拼 argv → spawn(rg)
  - read_file ↔ src/tools/FileReadTool/         读整篇、带预算截断

D1 任务在文件末尾：用 registry.register 把这两个函数声明成工具。
函数体本身已是可用实现，不用动；你写的是 @register 那层声明。
"""

import subprocess
from pathlib import Path

from registry import register
from state import READ_STATE, FileSeen

# 默认搜 "运行 agent 的当前目录"（它是个 coding agent，搜的就是你跑它的那个仓库）。
# 不写死任何绝对路径 —— 项目要能独立 clone 到任何机器就跑。
SEARCH_ROOT = "."
HEAD_LIMIT = 250  # 与 GrepTool.ts DEFAULT_HEAD_LIMIT=250 一致
MAX_FILE_CHARS = 8000  # 单篇预算（自定，非源码值）：本地小模型故意收紧


@register(
    "grep",
    "基于 ripgrep 的搜索；pattern 支持完整 regex；返回匹配文件路径列表；开放式查找多调几轮换 pattern 缩小",
    {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "ripgrep 正则；可用 a|b 这种分支写法把同义说法都覆盖到",
            },
            "glob": {
                "type": "string",
                "description": "文件名过滤，如 *.py、*.md；默认 *.md",
            },
            "path": {
                "type": "string",
                "description": "搜索的目录；默认当前目录（运行 agent 的那个仓库根）",
            },
        },
        "required": ["pattern"],
    },
    read_only=True,
)
def grep(pattern: str, glob: str = "*.md", path: str = SEARCH_ROOT) -> str:
    """调真 ripgrep。默认 files_with_matches（-l），和 GrepTool 默认一致。"""
    args = [
        "rg",
        "--hidden",
        "-l",
        "--glob",
        "!.git",
        "--max-columns",
        "500",
        "--glob",
        glob,
        pattern,
        path or SEARCH_ROOT,
    ]
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=20)
    except subprocess.TimeoutExpired:
        return "（ripgrep 超时）"
    files = [l for l in out.stdout.splitlines() if l.strip()][:HEAD_LIMIT]
    return "\n".join(files) if files else "（无匹配文件）"


@register(
    "read_file",
    "读取一个文件的完整内容（拿到 grep 命中的路径后用它读正文）",
    {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要读取的文件路径，通常是 grep 命中返回的那个路径",
            },
        },
        "required": ["path"],
    },
    read_only=True,
)
def read_file(path: str) -> str:
    """读整篇文件，带单篇预算截断。"""
    p = Path(path)
    if not p.exists():
        return f"（文件不存在: {path}）"
    text = p.read_text(encoding="utf-8")

    READ_STATE[str(p)] = FileSeen(mtime=p.stat().st_mtime, content=text)

    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + "\n…(已截断)"
    return text
