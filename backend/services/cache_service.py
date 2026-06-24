import json
import redis.asyncio as aioredis

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class CacheService:
    """Redis 缓存服务"""

    def __init__(self):
        self.redis: aioredis.Redis | None = None

    async def initialize(self):
        """初始化 Redis 连接"""
        try:
            self.redis = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                decode_responses=True,
            )
            await self.redis.ping()
            print(f"[OK] Redis 缓存服务就绪: {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            print(f"[WARN] Redis 连接失败: {e}，缓存功能禁用")
            self.redis = None

    async def get(self, key: str) -> dict | None:
        """获取缓存"""
        if not self.redis:
            return None
        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    async def set(self, key: str, value: dict, ttl: int | None = None) -> bool:
        """设置缓存"""
        if not self.redis:
            return False
        try:
            ttl = ttl or settings.redis_recommend_ttl
            await self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception:
            return False

    async def get_recommend_cache(self, user_id: str, history_hash: str) -> dict | None:
        """获取推荐缓存"""
        key = f"recommend:{user_id}:{history_hash}"
        return await self.get(key)

    async def set_recommend_cache(
        self, user_id: str, history_hash: str, data: dict
    ) -> bool:
        """设置推荐缓存"""
        key = f"recommend:{user_id}:{history_hash}"
        return await self.set(key, data, settings.redis_recommend_ttl)

    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.close()
