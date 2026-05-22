"""
service/idempotency.py

JVM ConcurrentHashMap.putIfAbsent  →  Python dict + threading.Lock.

The very first thing BridgeIngestionService does is call claim(hash).
Only the thread that wins the lock and finds the key absent gets True.
Every other thread (or later replay) gets False and is short-circuited
before any decryption or DB work.

In production: replace with Redis  SET key NX EX 86400
"""

import threading
import time

_seen: dict[str, int] = {}          # hash → epoch-seconds when claimed
_lock = threading.Lock()
TTL_SECONDS = 86_400                # 24 hours — matches freshness window


def claim(packet_hash: str) -> bool:
    """
    Try to claim packet_hash.
    Returns True (first claimer — proceed) or False (duplicate — drop).
    """
    now = int(time.time())
    with _lock:
        if packet_hash in _seen:
            return False
        _seen[packet_hash] = now
        return True


def evict_expired():
    """
    Remove entries older than TTL_SECONDS.
    Call periodically (e.g., from a background thread) to prevent unbounded growth.
    """
    cutoff = int(time.time()) - TTL_SECONDS
    with _lock:
        expired = [k for k, v in _seen.items() if v < cutoff]
        for k in expired:
            del _seen[k]


def reset():
    """Clear the entire cache — used by /api/mesh/reset."""
    with _lock:
        _seen.clear()


def size() -> int:
    with _lock:
        return len(_seen)
