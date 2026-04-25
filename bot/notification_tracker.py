"""
追踪 bot 发出的需要用户处理的通知消息。
record(mid, label) — 记录一条待处理通知
resolve(mid)       — 标记已处理
get_pending(hours) — 返回最近 hours 小时内仍未处理的消息列表
"""
import threading
from datetime import datetime, timedelta

_lock = threading.Lock()
_pending: dict[int, dict] = {}  # mid → {"time": datetime, "label": str}


def record(mid: int, label: str = "") -> None:
    if not mid:
        return
    with _lock:
        _pending[mid] = {"time": datetime.now(), "label": label}


def resolve(mid: int) -> None:
    with _lock:
        _pending.pop(mid, None)


def get_pending(hours: float = 1.0) -> list[dict]:
    cutoff = datetime.now() - timedelta(hours=hours)
    with _lock:
        return [
            {"mid": mid, **info}
            for mid, info in _pending.items()
            if info["time"] >= cutoff
        ]
