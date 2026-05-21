"""LLM 构造：把 client 和它该用的 model 捆绑在一起，一处切 provider。

用法：
    from llm import build_llm
    llm = build_llm()
    resp = llm.client.chat.completions.create(model=llm.model, messages=[...])

为什么 build_llm() -> LLM 而不是 build_client() + get_model()：
    "provider → (哪个 client, 哪个 model)" 是一个决策；拆成两个函数会 desync
    （build_client("ollama") 配 get_model("deepseek")）。frozen dataclass
    把它俩捆死，物理上无法分家。
"""

from dataclasses import dataclass
from typing import Literal

from openai import OpenAI

from config import DEEPSEEK_API_KEY

Provider = Literal["deepseek", "ollama"]

# 每个 provider 的接入配置（OpenAI 兼容协议，换厂商只换 base_url + model）
# context_window: 模型最大上下文窗口，用来算 context 使用率。来源是
# provider 官方文档(deepseek 1M 来自 api-docs.deepseek.com/quick_start/pricing
# 表格)。这是 provider 决策的一部分,跟 model 一起捆,不能 desync。
_CONFIG: dict[Provider, dict[str, str | int]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "context_window": 1_000_000,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        # ⚠️ 改成你 `ollama pull` 的确切 tag（ollama list / ollama.com/library 核对）
        "model": "qwen2.5:7b",
        "context_window": 32_000,
    },
}

# ★ 全项目单一切换点：改这一行 = 所有调用一起切（也可调用时传 provider 覆盖）
PROVIDER: Provider = "deepseek"


@dataclass(frozen=True)
class LLM:
    """client / model / 上下文窗口捆绑在一起，不可变，不可能 desync。"""

    client: OpenAI
    model: str
    context_window: int


def build_llm(provider: Provider = PROVIDER) -> LLM:
    """一次决策构造 LLM：deepseek 走云端（读 .env 的 key），ollama 走本地。"""
    cfg = _CONFIG[provider]
    # 本地 ollama 不校验 key，随便填；deepseek 从环境变量读
    api_key = DEEPSEEK_API_KEY if provider == "deepseek" else "ollama"
    base_url = cfg["base_url"]
    model = cfg["model"]
    context_window = cfg["context_window"]
    assert isinstance(base_url, str) and isinstance(model, str)
    assert isinstance(context_window, int)
    client = OpenAI(api_key=api_key, base_url=base_url)
    return LLM(client=client, model=model, context_window=context_window)
