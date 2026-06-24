import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.cache_service import CacheService


@pytest.fixture
def cache_service():
    svc = CacheService()
    svc.redis = AsyncMock()
    return svc


@pytest.mark.asyncio
async def test_get_returns_data(cache_service):
    test_data = {"user_id": "test", "recommendations": []}
    cache_service.redis.get = AsyncMock(return_value=json.dumps(test_data))

    result = await cache_service.get("test_key")
    assert result == test_data
    cache_service.redis.get.assert_called_once_with("test_key")


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(cache_service):
    cache_service.redis.get = AsyncMock(return_value=None)

    result = await cache_service.get("missing_key")
    assert result is None


@pytest.mark.asyncio
async def test_get_returns_none_when_no_redis():
    cache = CacheService()
    cache.redis = None

    result = await cache.get("any_key")
    assert result is None


@pytest.mark.asyncio
async def test_set_stores_data(cache_service):
    cache_service.redis.setex = AsyncMock(return_value=True)

    result = await cache_service.set("key", {"data": "value"}, ttl=60)
    assert result is True
    cache_service.redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_set_returns_false_when_no_redis():
    cache = CacheService()
    cache.redis = None

    result = await cache.set("key", {"data": "value"})
    assert result is False


@pytest.mark.asyncio
async def test_get_recommend_cache(cache_service):
    test_data = {"recommendations": [{"asin": "B001"}]}
    cache_service.redis.get = AsyncMock(return_value=json.dumps(test_data))

    result = await cache_service.get_recommend_cache("user1", "hash123")
    assert result == test_data
    cache_service.redis.get.assert_called_once_with("recommend:user1:hash123")


@pytest.mark.asyncio
async def test_set_recommend_cache(cache_service):
    cache_service.redis.setex = AsyncMock(return_value=True)

    result = await cache_service.set_recommend_cache("user1", "hash123", {"data": "test"})
    assert result is True
    cache_service.redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_close(cache_service):
    cache_service.redis.close = AsyncMock()
    await cache_service.close()
    cache_service.redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_when_no_redis():
    cache = CacheService()
    cache.redis = None
    # Should not raise
    await cache.close()
