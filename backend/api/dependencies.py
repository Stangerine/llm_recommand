from fastapi import Request

from services.sid_service import SIDService
from es_client.client import ESClient
from models.recommender_inference import RecommenderInference


def get_sid_service(request: Request) -> SIDService:
    return request.app.state.sid_svc


def get_es_client(request: Request) -> ESClient:
    return request.app.state.es_client


def get_recommender(request: Request) -> RecommenderInference:
    return request.app.state.recommender
