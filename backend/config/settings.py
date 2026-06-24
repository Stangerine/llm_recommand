from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Elasticsearch
    es_host: str = "http://localhost:9200"
    es_index_name: str = "industrial_products"
    es_timeout: int = 10

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_recommend_ttl: int = 300  # 推荐结果缓存 5 分钟
    redis_sid_ttl: int = 86400  # SID 映射缓存 24 小时
    redis_product_ttl: int = 3600  # 商品缓存 1 小时

    # 模型
    model_base: str = "Qwen/Qwen2.5-3B"
    model_lora_path: str = "./models/checkpoints/qwen25_rec_lora"
    rqvae_path: str = "./models/checkpoints/rqvae"
    model_device: str = "cuda"
    beam_search_num_beams: int = 20
    top_k: int = 10

    # Milvus
    milvus_uri: str = "products.db"
    milvus_collection: str = "products"
    milvus_sid_collection: str = "sid_mapping"

    # Embedding
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    embedding_batch_size: int = 128

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # 数据路径
    sid_mapping_path: str = "./data/processed/sid_mapping.json"
    products_path: str = "./data/processed/products.jsonl"


settings = Settings()
