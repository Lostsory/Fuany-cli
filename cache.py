"""通用缓存结构。

TTLCache: LRU 淘汰 + TTL 过期的字符串缓存。
对照 Claude Code src/tools/WebFetchTool/utils.ts:61-69 的 LRUCache
(ttl 15min + maxSize 50MB)。web_fetch 用它缓存抓取的 markdown:
重复 fetch 同 url 命中,翻页(不同 offset)也命中,都不重抓网络。
"""

import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class _Entry:
    value: str  # 缓存的字符串值
    ts: float  # 存入的时间戳
    size: int  # value 的 utf-8 字节数


class TTLCache:
    """LRU + TTL 的字符串缓存(key/value 都是 str)。

    两个独立淘汰维度:
      - TTL: 条目存活超 ttl 秒,get 时判过期当 miss
      - LRU: 总字节超 max_bytes 时,淘汰最久未用的(OrderedDict 头部)

    value 限定 str: max_bytes 按 value 的 utf-8 字节数累计,语义清晰
    (若 value 任意类型,大小不好算)。
    """

    def __init__(self, ttl: float, max_bytes: int):
        """初始化 TTLCache。

        Args:
            ttl: 每条缓存的存活秒数。
            max_bytes: 缓存占用最大字节数，超限时 LRU 淘汰。
        """
        self._ttl = ttl
        self._max_bytes = max_bytes
        self._data: OrderedDict[str, _Entry] = OrderedDict()
        self._bytes = 0

    def get(self, key: str) -> str | None:
        """读取缓存条目。

        若 key 不存在或已过期（超过 ttl），返回 None；
        否则将 key 移至最近使用位置并返回其值。

        Args:
            key: 缓存键。

        Returns:
            缓存的值，或 None（不存在/已过期）。
        """
        entry = self._data.get(key)
        if entry is None:
            return None
        if time.time() - entry.ts > self._ttl:
            self._evict(key)
            return None
        self._data.move_to_end(key)
        return entry.value

    def put(self, key: str, value: str) -> None:
        """写入缓存条目。

        若 key 已存在则先淘汰旧条目；新条目写入后，
        若总字节数超过 max_bytes，则从最久未用的条目开始淘汰，
        直到低于上限或只剩一个条目。

        Args:
            key: 缓存键。
            value: 要缓存的字符串值。
        """
        if key in self._data:
            self._evict(key)
        size = len(value.encode("utf-8"))
        self._data[key] = _Entry(value=value, ts=time.time(), size=size)
        self._bytes += size
        while self._bytes > self._max_bytes and len(self._data) > 1:
            self._evict(next(iter(self._data)))

    def _evict(self, key: str) -> None:
        """从缓存中移除指定条目，并扣减字节计数。"""
        self._bytes -= self._data.pop(key).size
