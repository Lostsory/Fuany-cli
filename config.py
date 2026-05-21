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

# === 子 agent 行为 ===
DEFAULT_MAX_TURNS_SUBAGENT: Final[int] = int(
    os.getenv("MINI_CC_MAX_TURNS_SUBAGENT", "50")
)
"""子 agent 默认迭代上限。对照 Hermes delegate_tool.py:512 DEFAULT_MAX_ITERATIONS=50。"""

# === 测试 hook ===
AUTO_ALLOW: Final[bool] = os.getenv("MINI_CC_AUTO_ALLOW", "").lower() in (
    "1",
    "true",
    "yes",
)
"""跳过权限门(CI / 非交互测试用,生产永不开)。"""

# === 子 agent 安全边界 ===
SUBAGENT_BLOCKED: Final[frozenset[str]] = frozenset()
"""子 agent 不可访问的工具(硬编码 invariant)。

对照 Hermes delegate_tool.py:44 DELEGATE_BLOCKED_TOOLS。
D6-② 时 = frozenset({"task"}) 防递归;D6-③ 清空,真递归防御由
tools/task.py 内的 depth 守卫接管(深度超阈值返回错误,模型自愈)。

故意不走 env:这是安全 invariant 边界,未来添加 blocked 工具时在此显式加。
"""

#
MAX_SUBAGENT_DEPTH: Final[int] = int(os.getenv("MINI_CC_MAX_SUBAGENT_DEPTH", "2"))

SYSTEM: Final[str] = (
    "你是一个交互式编码助手，帮用户做软件工程任务。"
    "使用下面的指引和可用工具(动态注册,见 tools=)来协助用户。"
    "\n\n"
    "## 工具使用\n"
    "- 简单问候直接回应，不必调工具。\n"
    "- **修改/写入文件前先读它**(read_file 看清当前内容,再 edit/write)。\n"
    "- 不要假设目录结构,先 glob/bash 看现状再动手。\n"
    "- 工具被拒绝(用户拒、未知工具、参数错)就**别重复同样调用** —— 想想原因再换方式。\n"
    "\n"
    "## 完成任务\n"
    "- 回答基于实际读到的内容;不知道就直说,不要编造。\n"
    "- 不要做超出请求范围的‘改进’(不加未要求的注释、不预制抽象)。"
)

SUBAGENT_SYSTEM: Final[str] = (
    "你是被委派执行特定任务的子 agent。"
    "专注完成委派给你的任务,完成后给一个简洁的最终答复。"
    "\n\n"
    "## 工具使用\n"
    "- **修改/写入文件前先读它**(read_file 看清当前内容,再 edit/write)。\n"
    "- 不要假设目录结构,先 glob/bash 看现状再动手。\n"
    "- 工具被拒绝就别重复同样调用,想想原因换方式。\n"
    "\n"
    "## 完成任务\n"
    "- 回答基于实际读到的内容;不知道就直说,不要编造。\n"
    "- 完成时输出一段总结,**不要继续调工具**。\n"
    "- 不要做超出请求范围的改进。"
)
