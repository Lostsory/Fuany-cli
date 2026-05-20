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

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI

Provider = Literal["deepseek", "ollama"]

# 每个 provider 的接入配置（OpenAI 兼容协议，换厂商只换 base_url + model）
_CONFIG: dict[Provider, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        # ⚠️ 改成你 `ollama pull` 的确切 tag（ollama list / ollama.com/library 核对）
        "model": "qwen2.5:7b",
    },
}

# ★ 全项目单一切换点：改这一行 = 所有调用一起切（也可调用时传 provider 覆盖）
PROVIDER: Provider = "deepseek"


@dataclass(frozen=True)
class LLM:
    """client 和它该用的 model 捆绑在一起，不可变，不可能 desync。"""

    client: OpenAI
    model: str


def build_llm(provider: Provider = PROVIDER) -> LLM:
    """一次决策构造 LLM：deepseek 走云端（读 .env 的 key），ollama 走本地。"""
    load_dotenv()
    cfg = _CONFIG[provider]
    # 本地 ollama 不校验 key，随便填；deepseek 从环境变量读
    api_key = os.getenv("DEEPSEEK_API_KEY") if provider == "deepseek" else "ollama"
    client = OpenAI(api_key=api_key, base_url=cfg["base_url"])
    return LLM(client=client, model=cfg["model"])
