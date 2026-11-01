"""工具调用日志：每次调用写入一条 JSON，便于逐行读取和检索。

LOG_PAYLOADS 控制是否记录参数和返回正文；关闭时只保留时间、工具名和
派发标志。LOG_STDOUT 控制输出位置：开启时写标准输出，否则追加到本地文件。
两项配置都由 config.py 在启动时读取。
"""

import json
from datetime import datetime
from pathlib import Path

from config import LOG_PAYLOADS, LOG_STDOUT

# 默认日志跟随模块所在目录，不受启动命令的当前工作目录影响。
LOG_FILE = Path(__file__).parent / "mini_cc.log"


def log(name: str, *, args: dict, result: str, dispatched: bool) -> None:
    """记录一次工具调用，包括被拒绝或参数错误的调用。

    name 是注册表中的工具名，args 是调用参数，result 是返回文本。
    dispatched 是注册表提供的派发标志，不代表工具返回的业务结果一定成功。
    """
    entry = {
        # 使用本机时间，精确到秒；此时间字符串不包含时区偏移。
        "ts": datetime.now().isoformat(timespec="seconds"),
        "tool": name,
        "dispatched": dispatched,
    }
    if LOG_PAYLOADS:
        # 参数原样记录，返回正文最多保留 500 个字符；截断不等于敏感信息脱敏。
        entry["args"] = args
        entry["result"] = result[:500] + ("...(截)" if len(result) > 500 else "")
    if LOG_STDOUT:
        # 保留中文并立即刷新，方便外部日志收集器及时读取；此分支不再写文件。
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        return
    # JSON Lines 格式：一条记录占一行，追加写入；本模块不负责日志轮转。
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # 直接执行本文件时写一条示例日志，输出位置仍由上述配置决定。
    log(
        "test",
        args={"message": "日志测试"},
        result="日志测试成功",
        dispatched=True,
    )
