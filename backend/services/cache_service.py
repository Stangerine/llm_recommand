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

    # ── 商品缓存 ──────────────────────────────────────────────

    async def get_product(self, asin: str) -> dict | None:
        """获取单个商品缓存"""
        return await self.get(f"product:{asin}")

    async def set_product(self, asin: str, data: dict) -> bool:
        """设置单个商品缓存"""
        return await self.set(f"product:{asin}", data, settings.redis_product_ttl)

    async def get_products_batch(self, asins: list[str]) -> dict[str, dict]:
        """批量获取商品缓存，返回 {asin: data}"""
        if not self.redis or not asins:
            return {}
        try:
            keys = [f"product:{a}" for a in asins]
            values = await self.redis.mget(keys)
            result = {}
            for asin, val in zip(asins, values):
                if val:
                    result[asin] = json.loads(val)
            return result
        except Exception:
            return {}

    async def set_products_batch(self, products: list[dict]) -> bool:
        """批量设置商品缓存"""
        if not self.redis or not products:
            return False
        try:
            pipe = self.redis.pipeline()
            for p in products:
                asin = p.get("asin", "")
                if asin:
                    pipe.setex(f"product:{asin}", settings.redis_product_ttl, json.dumps(p))
            await pipe.execute()
            return True
        except Exception:
            return False

    # ── SID 缓存 ─────────────────────────────────────────────

    async def get_sid(self, asin: str) -> str | None:
        """获取单个 SID 缓存"""
        if not self.redis:
            return None
        try:
            return await self.redis.get(f"sid:{asin}")
        except Exception:
            return None

    async def set_sid(self, asin: str, sid: str) -> bool:
        """设置单个 SID 缓存"""
        if not self.redis:
            return False
        try:
            await self.redis.setex(f"sid:{asin}", settings.redis_sid_ttl, sid)
            return True
        except Exception:
            return False

    async def get_sids_batch(self, asins: list[str]) -> dict[str, str]:
        """批量获取 SID 缓存，返回 {asin: sid}"""
        if not self.redis or not asins:
            return {}
        try:
            keys = [f"sid:{a}" for a in asins]
            values = await self.redis.mget(keys)
            result = {}
            for asin, val in zip(asins, values):
                if val:
                    result[asin] = val
            return result
        except Exception:
            return {}

    async def set_sids_batch(self, mappings: dict[str, str]) -> bool:
        """批量设置 SID 缓存，mappings = {asin: sid}"""
        if not self.redis or not mappings:
            return False
        try:
            pipe = self.redis.pipeline()
            for asin, sid in mappings.items():
                pipe.setex(f"sid:{asin}", settings.redis_sid_ttl, sid)
            await pipe.execute()
            return True
        except Exception:
            return False

    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.close()
