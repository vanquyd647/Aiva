"""Cache service tests."""

import pytest

from app.services.cache import CacheService


@pytest.mark.anyio
async def test_memory_cache_json_roundtrip() -> None:
    cache = CacheService(redis_url=None)
    await cache.startup()

    await cache.set_json("k1", {"ok": True}, ttl_seconds=5)
    value = await cache.get_json("k1")

    assert value == {"ok": True}


@pytest.mark.anyio
async def test_memory_cache_counter_and_prefix_delete() -> None:
    cache = CacheService(redis_url=None)
    await cache.startup()

    assert await cache.increment("rate:login", ttl_seconds=60) == 1
    assert await cache.increment("rate:login", ttl_seconds=60) == 2

    await cache.set_json("users:list:1", {"items": []}, ttl_seconds=60)
    await cache.set_json("users:list:2", {"items": []}, ttl_seconds=60)
    await cache.delete_prefix("users:list:")

    assert await cache.get_json("users:list:1") is None
    assert await cache.get_json("users:list:2") is None
