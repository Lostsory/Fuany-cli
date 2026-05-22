"""load_skill 工具:渐进披露 Layer 2,按需读 skill 全文。

对照 CC SkillTool.ts —— 模型看 listing(Layer 1)决定加载,调本工具读全文。
"""

from registry import register
from skills import load_skill_body


@register(
    "load_skill",
    "加载一个 skill 的完整指南。先看 system 里的可用 skill 列表,需要某个时用它的 name 调本工具。",
    {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "skill 名字(system 里 skill 列表给出的)",
            },
        },
        "required": ["name"],
    },
    read_only=True,  # 只读,不弹权限门,可并行
)
def load_skill(name: str) -> str:
    body = load_skill_body(name)
    return body if body else f"未找到 skill: {name}（用 system 里列出的确切 name）"
