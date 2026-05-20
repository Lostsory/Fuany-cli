"""shell 工具：在 shell 中跑命令。

对照 Claude Code：src/tools/BashTool/BashTool.tsx —— exec(command, 'bash', {timeout});
sandbox / 后台任务 / sed 预览属 D3+，本最小版不做。
"""

import subprocess

from registry import register

DEFAULT_TIMEOUT = 120
MAX_TIMEOUT = 600
OUTPUT_LIMIT = 8000


def _section(text: str) -> str:
    if not text:
        return "（空）"
    if len(text) > OUTPUT_LIMIT:
        return text[:OUTPUT_LIMIT] + f"\n（已截断，共 {len(text)} 字符）"
    return text


@register(
    "bash",
    f"在 shell 中执行命令。返回退出码、stdout、stderr。"
    f"timeout 单位秒，默认 {DEFAULT_TIMEOUT}、最大 {MAX_TIMEOUT}；"
    f"stdout/stderr 各截断 {OUTPUT_LIMIT} 字符。",
    {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数；不传用默认（见工具说明）",
            },
            "description": {
                "type": "string",
                "description": "一句话说明本次命令在做什么（如「跑单元测试」「列出当前目录」），用于打日志；可选，琐碎命令可省。",
            },
        },
        "required": ["command"],
    },
)
def bash(command: str, description: str = "", timeout: int = DEFAULT_TIMEOUT) -> str:
    try:
        ans = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, MAX_TIMEOUT),
        )
    except subprocess.TimeoutExpired:
        return "命令执行超时"

    return (
        f"[exit {ans.returncode}]\n"
        f"[stdout]\n{_section(ans.stdout)}\n"
        f"[stderr]\n{_section(ans.stderr)}"
    )
