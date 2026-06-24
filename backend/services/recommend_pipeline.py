import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.sid_service import SIDService
from es_client.client import ESClient
from models.recommender_inference import RecommenderInference


class RecommendPipeline:
    """推荐流水线：串联 SID 映射、模型推理、ES 回查"""

    def __init__(
        self,
        sid_service: SIDService,
        es_client: ESClient,
        recommender: RecommenderInference,
    ):
        self.sid_service = sid_service
        self.es_client = es_client
        self.recommender = recommender

    async def recommend(
        self,
        history_asins: list[str],
        top_k: int = 10,
    ) -> list[dict]:
        """
        完整推荐流程：
        1. ASIN → SID 序列
        2. 模型推理 → 候选 SID
        3. SID → ASIN
        4. ES 批量回查
        5. 排序返回
        """
        # 1. ASIN → SID
        history_sids = self.sid_service.asins_to_sids(history_asins)
        if not history_sids:
            raise ValueError("历史商品均无对应 SID")

        # 2. 模型推理
        candidate_sids = self.recommender.predict(history_sids)

        # 3. SID → ASIN
        candidate_asins = self.sid_service.sids_to_asins(candidate_sids)
        if not candidate_asins:
            raise ValueError("模型未生成有效候选")

        # 4. ES 回查
        products = await self.es_client.get_products_by_asins(candidate_asins[:top_k])

        # 5. 排序
        order = {asin: i for i, asin in enumerate(candidate_asins)}
        products.sort(key=lambda p: order.get(p["asin"], 999))

        return products
