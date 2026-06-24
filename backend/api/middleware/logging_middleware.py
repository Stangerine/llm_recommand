import time
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from collections import defaultdict

logger = structlog.get_logger()


class MetricsCollector:
    """指标收集器，可接入 Prometheus"""

    def __init__(self):
        self.recommend_latency: list[float] = []
        self.model_inference_ms: list[float] = []
        self.es_query_ms: list[float] = []
        self.sid_hit_count: int = 0
        self.sid_miss_count: int = 0
        self.recommend_empty_count: int = 0
        self.recommend_request_total: int = 0

    def record_recommend_latency(self, ms: float):
        self.recommend_latency.append(ms)
        self.recommend_request_total += 1

    def record_model_inference(self, ms: float):
        self.model_inference_ms.append(ms)

    def record_es_query(self, ms: float):
        self.es_query_ms.append(ms)

    def record_sid_hit(self, hit: bool):
        if hit:
            self.sid_hit_count += 1
        else:
            self.sid_miss_count += 1

    def record_recommend_empty(self):
        self.recommend_empty_count += 1

    def get_sid_hit_rate(self) -> float:
        total = self.sid_hit_count + self.sid_miss_count
        return self.sid_hit_count / total if total > 0 else 0.0

    def get_stats(self) -> dict:
        return {
            "recommend_request_total": self.recommend_request_total,
            "recommend_empty_count": self.recommend_empty_count,
            "sid_hit_rate": round(self.get_sid_hit_rate(), 4),
            "avg_recommend_latency_ms": (
                round(sum(self.recommend_latency) / len(self.recommend_latency), 2)
                if self.recommend_latency
                else 0
            ),
            "avg_model_inference_ms": (
                round(sum(self.model_inference_ms) / len(self.model_inference_ms), 2)
                if self.model_inference_ms
                else 0
            ),
            "avg_es_query_ms": (
                round(sum(self.es_query_ms) / len(self.es_query_ms), 2)
                if self.es_query_ms
                else 0
            ),
        }


# 全局指标收集器
metrics = MetricsCollector()


class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件，记录耗时和关键指标"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        # 记录推荐接口指标
        if request.url.path == "/api/v1/recommend" and request.method == "POST":
            metrics.record_recommend_latency(duration_ms)

        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
