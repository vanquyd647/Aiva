"""Cache service backed by Redis with in-memory fallback."""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None


@dataclass
class _MemoryValue:
    value: str
    expires_at: float


class _MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, _MemoryValue] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        async with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            if item.expires_at < time.time():
                self._store.pop(key, None)
                return None
            return item.value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        async with self._lock:
            self._store[key] = _MemoryValue(
                value=value,
                expires_at=time.time() + ttl_seconds,
            )

    async def delete_prefix(self, prefix: str) -> None:
        async with self._lock:
            for key in list(self._store.keys()):
                if key.startswith(prefix):
                    self._store.pop(key, None)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        async with self._lock:
            now = time.time()
            item = self._store.get(key)
            if not item or item.expires_at < now:
                self._store[key] = _MemoryValue(value="1", expires_at=now + ttl_seconds)
                return 1
            current = int(item.value) + 1
            self._store[key] = _MemoryValue(value=str(current), expires_at=item.expires_at)
            return current


class CacheService:
    def __init__(self, redis_url: str | None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._memory = _MemoryCache()
        self.mode = "memory"

    async def startup(self) -> None:
        if not self._redis_url or redis is None:
            return
        try:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            await self._redis.ping()
            self.mode = "redis"
        except Exception:
            self._redis = None
            self.mode = "memory"

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.close()

    async def get_json(self, key: str) -> Any | None:
        if self._redis is not None:
            raw = await self._redis.get(key)
        else:
            raw = await self._memory.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        payload = json.dumps(value)
        if self._redis is not None:
            await self._redis.set(key, payload, ex=ttl_seconds)
            return
        await self._memory.set(key, payload, ttl_seconds)

    async def delete_prefix(self, prefix: str) -> None:
        if self._redis is not None:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(cursor=cursor, match=f"{prefix}*")
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
            return
        await self._memory.delete_prefix(prefix)

    async def increment(self, key: str, ttl_seconds: int) -> int:
        if self._redis is not None:
            pipe = self._redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, ttl_seconds)
            result = await pipe.execute()
            return int(result[0])
        return await self._memory.incr(key, ttl_seconds)


cache = CacheService(settings.REDIS_URL)
