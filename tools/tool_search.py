"""tool_search 工具: Codex 风格 deferred tool 发现。

注册表保存所有工具；本工具只返回 deferred 工具的轻量匹配结果。
agent loop 看到 matches 后,下一轮才把对应完整 schema 放进 tools=。
"""

import json

from registry import register, search_deferred_tools


@register(
    "tool_search",
    "搜索尚未直接加载的 deferred tools。需要 web、委派、低频能力但当前 tools 里没有时先用它。",
    {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索词,例如 web/search/fetch/task/agent/delegate",
            },
            "limit": {
                "type": "integer",
                "description": "最多返回几个工具,默认 5,最大 20",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    read_only=True,
)
def tool_search(query: str, limit: int = 5) -> str:
    matches = search_deferred_tools(query, limit)
    return json.dumps(
        {
            "matches": [match["name"] for match in matches],
            "tools": matches,
            "note": "这些工具会在下一轮请求中加载完整 schema; 然后可直接调用。",
        },
        ensure_ascii=False,
    )
