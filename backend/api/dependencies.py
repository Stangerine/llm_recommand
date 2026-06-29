from fastapi import Request

from services.sid_service import SIDService
from services.search_service import SearchService
from es_client.client import ESClient
from models.recommender_inference import RecommenderInference


def get_sid_service(request: Request) -> SIDService:
    return request.app.state.sid_svc


def get_es_client(request: Request) -> ESClient:
    return request.app.state.es_client


def get_recommender(request: Request) -> RecommenderInference:
    return request.app.state.recommender


def get_search_service(request: Request) -> SearchService:
    return SearchService(
        es_client=request.app.state.es_client,
        embedding_svc=request.app.state.embedding_svc,
        vector_svc=request.app.state.vector_svc,
    )
