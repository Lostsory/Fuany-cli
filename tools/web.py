import httpx
from markdownify import markdownify

from cache import TTLCache
from config import BRAVE_SEARCH_API_KEY
from llm import build_llm
from registry import register

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
MAX_MARKDOWN_LENGTH = 100_000
CACHE_TTL = 15 * 60  # 15min
CACHE_MAX_BYTES = 50 * 1024 * 1024  # 50MB

_url_cache = TTLCache(ttl=CACHE_TTL, max_bytes=CACHE_MAX_BYTES)


@register(
    "web_search",
    "用 Brave 搜索网络,返回标题+url+摘要。查最新信息/文档/事实时用,之后可用 web_fetch 读详情。",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索词"},
            "limit": {"type": "integer", "description": "结果数(默认 5,最多 10)"},
        },
        "required": ["query"],
    },
    read_only=True,
)
def web_search(query: str, limit: int = 5) -> str:
    if not BRAVE_SEARCH_API_KEY:
        return "错误: 未配置 BRAVE_SEARCH_API_KEY（在 .env 里加）"
    limit = min(max(limit, 1), 10)

    try:
        resp = httpx.get(
            BRAVE_ENDPOINT,
            params={"q": query, "count": limit},
            headers={
                "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
                "Accept": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"搜索失败: {e.response.status_code}（401=key 错, 429=限流）"
    except httpx.HTTPError as e:
        return f"搜索失败: {e}"

    results = resp.json().get("web", {}).get("results", [])

    if not results:
        return "未找到相关结果"

    return "\n".join(
        f"- {r.get('title', '')}\n  {r.get('url', '')}\n  {r.get('description', '')}"
        for r in results[:limit]
    )


@register(
    "web_fetch",
    "抓取一个 URL 的内容并按 prompt 提炼。通常先 web_search 拿到 url,再用本工具读详情。",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的网址"},
            "prompt": {
                "type": "string",
                "description": "对网页内容要做什么(提炼/回答什么问题)",
            },
            "offset": {
                "type": "integer",
                "description": "从第几个字符开始读(默认 0)。网页超长被截断时,看返回的分页提示用 offset 翻页读后续",
                "default": 0,
            },
        },
        "required": ["url", "prompt"],
    },
    read_only=True,
)
def web_fetch(url: str, prompt: str, offset: int = 0) -> str:
    # 查缓存(对照 CC URL_CACHE;命中则不重抓 —— 翻页/重复 fetch 都受益)
    md = _url_cache.get(url)

    if md is None:
        # httpx GET,不自动跟随 redirect(对照 CC 跨 host SSRF 防护)
        try:
            resp = httpx.get(url, timeout=15, follow_redirects=False)
        except httpx.HTTPError as e:
            return f"抓取失败: {e}"

        # 跨 host redirect → 返回提示让模型再 fetch(对照 CC WebFetchTool.ts:217-235)
        if resp.is_redirect:
            location = resp.headers.get("location", "")
            return (
                f"REDIRECT: {url} 跳转到 {location}。"
                f"请用 web_fetch 重新抓取 {location}（同样的 prompt）。"
            )

        # HTML → markdown(对照 CC Turndown)
        content_type = resp.headers.get("content-type", "")
        md = markdownify(resp.text) if "html" in content_type else resp.text
    # 截断
    total = len(md)
    page = md[offset : offset + MAX_MARKDOWN_LENGTH]

    # 调 DeepSeek 小模型按 prompt 提炼(对照 CC applyPromptToMarkdown/queryHaiku)
    llm = build_llm()
    out = llm.client.chat.completions.create(
        model=llm.model,
        messages=[
            {
                "role": "system",
                "content": "你是网页内容提炼助手。只基于给定网页 markdown 内容,按用户任务提炼/回答,不编造网页里没有的信息。",
            },
            {"role": "user", "content": f"网页内容:\n{page}\n\n任务:{prompt}"},
        ],
    )
    ans = out.choices[0].message.content or "(无提炼结果)"

    end = offset + len(page)
    footer = f"\n\n---\n[网页共 {total} 字符,本次读取 [{offset}, {end})。"
    footer += (
        f"还有未读内容,用 web_fetch(url 不变, offset={end}) 继续读。]"
        if end < total
        else "已到末尾。]"
    )
    return ans + footer
