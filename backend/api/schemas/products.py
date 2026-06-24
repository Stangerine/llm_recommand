from pydantic import BaseModel


class ProductDetail(BaseModel):
    asin: str
    title: str
    description: str | None = None
    category: str | None = None
    brand: str | None = None
    price: float | None = None
    rating: float | None = None
    rating_count: int | None = None


class SearchResponse(BaseModel):
    results: list[ProductDetail]
    total: int
    query: str = ""
    search_mode: str = "keyword"  # "keyword" | "vector" | "hybrid"


class ProductListResponse(BaseModel):
    products: list[ProductDetail]
    total: int
    page: int
    page_size: int
    total_pages: int


class BehaviorRequest(BaseModel):
    user_id: str
    asin: str
    action_type: str  # view, click, purchase
