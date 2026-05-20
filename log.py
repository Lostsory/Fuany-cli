import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent / "mini_cc.log"


def log(name: str, *, args: dict, result: str, dispatched: bool) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "tool": name,
        "args": args,
        "dispatched": dispatched,
        "result": result[:500] + ("...(截)" if len(result) > 500 else ""),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
