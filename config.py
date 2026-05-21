"""mini-cc 配置:所有 env 读取的单一入口。

设计哲学:
- env 在模块加载时一次性读取(fail-loud,格式错立刻崩,不拖到运行时)
- 类型化常量,业务代码不直接见 os.getenv
- README 写"看 config.py 即可知道所有支持的 env"

对照 Hermes config.yaml 的角色,但 mini-cc 走 env(更轻,deploy 友好)。
"""

import os
from typing import Final

from dotenv import load_dotenv

load_dotenv()

# === Provider 凭证 ===
DEEPSEEK_API_KEY: Final[str | None] = os.getenv("DEEPSEEK_API_KEY")


# === Agent 行为 ===
DEFAULT_MAX_TURNS: Final[int] = int(os.getenv("MINI_CC_MAX_TURNS", "90"))
"""父 agent 默认迭代上限。对照 Hermes IterationBudget 父 90。"""


# === 测试 hook ===
AUTO_ALLOW: Final[bool] = os.getenv("MINI_CC_AUTO_ALLOW", "").lower() in (
    "1",
    "true",
    "yes",
)
"""跳过权限门(CI / 非交互测试用,生产永不开)。"""
