import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent / "mini_cc.log"


def _log(name: str, args: dict, result: str, ok: bool) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "tool": name,
        "args": args,
        "ok": ok,
        "result": result[:500] + ("...(截)" if len(result) > 500 else ""),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
