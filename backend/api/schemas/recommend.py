from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    user_id: str
    history_asins: list[str] = Field(..., min_length=1, max_length=50)
    top_k: int = Field(default=10, ge=1, le=50)


class ProductInfo(BaseModel):
    asin: str
    title: str
    description: str | None = None
    category: str | None = None
    brand: str | None = None
    price: float | None = None
    rating: float | None = None
    rating_count: int | None = None


class RecommendResponse(BaseModel):
    user_id: str
    recommendations: list[ProductInfo]
    total: int
    model_version: str = "qwen2.5-3b-sft-grpo-v1"
