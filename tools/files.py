"""文件工具组：write（写）、edit（局部替换）、glob（按文件名模式找）。

对照 Claude Code：
  - write ↔ src/tools/FileWriteTool/FileWriteTool.ts —— call 即 writeTextContent
  - edit  ↔ src/tools/FileEditTool/FileEditTool.ts  —— 唯一匹配；replace_all 才允许多处
  - glob  ↔ src/tools/GlobTool/GlobTool.ts          —— pattern + 可选 path 的 glob

权限门:registry.py call_tool 派发前调 _ask_permission。
mod-time 守卫(D3 + D6 强化):write/edit 前比对 read_state 的 mtime+content
防外部偷改;read_state 在 D6 改 ContextVar,每 agent 独立隔离。
"""

from pathlib import Path

from registry import register
from state import FileSeen, get_read_state

GLOB_LIMIT = 100
SEARCH_ROOT = "."


@register(
    "write",
    "向本地文件系统写入一个文件。",
    {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要写入的文件路径（绝对路径，不要用相对路径）",
            },
            "content": {
                "type": "string",
                "description": "要写入文件的完整内容",
            },
        },
        "required": ["path", "content"],
    },
)
def write(path: str, content: str) -> str:
    p = Path(path)
    # mod-time + content 双比对（CC FileWriteTool 风格）
    read_state = get_read_state()
    if p.exists() and str(p) not in read_state:
        return f"错误: 文件 {path} 已存在但未读过,必须先 read_file 才能覆盖。"
    if str(p) in read_state:
        seen = read_state[str(p)]
        if p.stat().st_mtime != seen.mtime:
            if p.read_text(encoding="utf-8") != seen.content:
                return f"文件已被外部修改自上次读取: {path}。请先 read_file 确认当前内容再写。"

    try:
        p.write_text(content, encoding="utf-8")
    except OSError as e:
        return f"写入失败: {str(e)}"

    read_state[str(p)] = FileSeen(mtime=p.stat().st_mtime, content=content)
    return f"已写入 {path} ({len(content)} 字符)"


@register(
    "edit",
    "对文件做局部编辑：查找 old_string（必须唯一匹配），替换为 new_string。"
    "适合小幅修改，大幅改动建议用 write 全量重写。",
    {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "要修改的文件路径（绝对路径）",
            },
            "old_string": {
                "type": "string",
                "description": "要被替换掉的原文本",
            },
            "new_string": {
                "type": "string",
                "description": "替换成的新文本（必须与 old_string 不同）",
            },
            "replace_all": {
                "type": "boolean",
                "description": "是否替换 old_string 的所有出现处（默认 False）",
                "default": False,
            },
        },
        "required": ["path", "old_string", "new_string"],
    },
)
def edit(path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    p = Path(path)

    if not p.exists():
        return f"文件不存在: {path}"

    text = p.read_text(encoding="utf-8")

    read_state = get_read_state()
    if str(p) not in read_state:
        return f"错误: 必须先 read_file('{path}') 才能 edit。"  # ← 强守卫
    seen = read_state[str(p)]
    if seen.mtime != p.stat().st_mtime and seen.content != text:
        return (
            f"文件已被外部修改自上次读取: {path}。请先 read_file 确认当前内容再编辑。"
        )

    count = text.count(old_string)

    if count == 0:
        return f"未找到要替换的字符串: {old_string}"
    if count > 1 and not replace_all:
        return f"（编辑失败：old_string 在文件中出现 {count} 次，不唯一。请提供更多上下文以精确定位）"

    new_text = text.replace(old_string, new_string)
    try:
        p.write_text(new_text, encoding="utf-8")
    except OSError as e:
        return f"写入失败: {str(e)}"

    read_state[str(p)] = FileSeen(mtime=p.stat().st_mtime, content=new_text)
    return f"已编辑 {path}（替换 {count} 处，共 {len(new_text)} 字符）"


@register(
    "glob",
    "按 glob 模式查找文件名。返回匹配的路径（每行一个）。"
    "和 grep 不同：grep 找文件内容，glob 只看文件名。"
    "递归用 `**`，如 `**/*.py` 找所有 Python 文件；`*.md` 只匹配当前目录直接子文件。",
    {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "glob 模式，如 `**/*.py`（递归）、`*.md`（只当前目录）",
            },
            "path": {
                "type": "string",
                "description": "搜索的根目录；默认当前目录（运行 agent 的仓库根）",
            },
        },
        "required": ["pattern"],
    },
    read_only=True,
)
def glob(pattern: str, path: str = SEARCH_ROOT) -> str:
    files = list(Path(path).glob(pattern))[:GLOB_LIMIT]

    if len(files) == 0:
        return "未找到匹配的文件"
    return "\n".join(str(f) for f in files)
