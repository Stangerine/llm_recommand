import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class SIDService:
    """
    SID 映射服务：Milvus 主存储 + Redis 热点缓存 + JSON 降级。
    按需查询，不在启动时全量加载。
    """

    def __init__(self, vector_service=None, cache_service=None):
        self._vector_svc = vector_service
        self._cache_svc = cache_service
        self._fallback_data = None  # JSON 降级数据

    async def initialize(self):
        """初始化：尝试从 JSON 加载降级数据"""
        try:
            with open(settings.sid_mapping_path) as f:
                self._fallback_data = json.load(f)
            print(f"[OK] SID 降级数据已加载: {len(self._fallback_data['asin2sid'])} 个商品")
        except Exception:
            self._fallback_data = None
            print("[WARN] SID 降级数据不可用")

    async def asin_to_sid(self, asin: str) -> str | None:
        """单个 ASIN → SID 转换（Redis → Milvus → JSON 降级）"""
        # 1. 查 Redis
        if self._cache_svc:
            cached = await self._cache_svc.get_sid(asin)
            if cached:
                return cached

        # 2. 查 Milvus
        if self._vector_svc and self._vector_svc.is_available():
            results = self._vector_svc.get_sids_by_asins([asin])
            if results:
                sid = results[0]["sid"]
                if self._cache_svc:
                    await self._cache_svc.set_sid(asin, sid)
                return sid

        # 3. JSON 降级
        if self._fallback_data:
            return self._fallback_data["asin2sid"].get(asin)

        return None

    async def asins_to_sids(self, asins: list[str]) -> list[str]:
        """批量 ASIN → SID 转换（Redis → Milvus → JSON 降级）"""
        result_map = {}
        missing = list(asins)

        # 1. 批量查 Redis
        if self._cache_svc and missing:
            cached = await self._cache_svc.get_sids_batch(missing)
            result_map.update(cached)
            missing = [a for a in missing if a not in cached]

        # 2. 批量查 Milvus
        if self._vector_svc and self._vector_svc.is_available() and missing:
            milvus_results = self._vector_svc.get_sids_by_asins(missing)
            to_cache = {}
            for r in milvus_results:
                result_map[r["asin"]] = r["sid"]
                to_cache[r["asin"]] = r["sid"]
            if self._cache_svc and to_cache:
                await self._cache_svc.set_sids_batch(to_cache)
            missing = [a for a in missing if a not in to_cache]

        # 3. JSON 降级
        if self._fallback_data and missing:
            for a in missing:
                sid = self._fallback_data["asin2sid"].get(a)
                if sid:
                    result_map[a] = sid

        return [result_map[a] for a in asins if a in result_map]

    async def sids_to_asins(self, sids: list[str]) -> list[str]:
        """批量 SID → ASIN 反查（Redis → Milvus → JSON 降级）"""
        result_map = {}
        missing = list(sids)

        # 1. 批量查 Redis（SID→ASIN 方向没有直接缓存，跳过）
        # SID→ASIN 的 Redis 缓存 key 需要反向设计，暂不缓存此方向

        # 2. Milvus 反查：先通过 SID 集合查询
        if self._vector_svc and self._vector_svc.is_available() and missing:
            # Milvus SID 集合按 SID 过滤
            try:
                escaped = [f'"{s}"' for s in missing]
                filter_expr = f'sid in [{", ".join(escaped)}]'
                results = self._vector_svc._client.query(
                    collection_name=settings.milvus_sid_collection,
                    filter=filter_expr,
                    output_fields=["asin", "sid"],
                )
                for r in results:
                    result_map[r["sid"]] = r["asin"]
            except Exception:
                pass

        # 3. JSON 降级
        if self._fallback_data and missing:
            for s in missing:
                asin = self._fallback_data["sid2asin"].get(s)
                if asin:
                    result_map[s] = asin

        return [result_map[s] for s in sids if s in result_map]

    def is_valid_sid(self, sid: str) -> bool:
        """检查 SID 是否有效（同步方法，仅用于模型推理）"""
        # 模型推理时需要同步检查，使用 JSON 降级数据
        if self._fallback_data:
            return sid in self._fallback_data["sid2asin"]
        return False

    def get_all_valid_sids(self) -> list[str]:
        """获取全部有效 SID（用于模型加载）"""
        if self._fallback_data:
            return list(self._fallback_data["sid2asin"].keys())
        # 如果没有降级数据，尝试从 Milvus 获取
        if self._vector_svc and self._vector_svc.is_available():
            results = self._vector_svc.get_all_sids()
            return [r["sid"] for r in results]
        return []
