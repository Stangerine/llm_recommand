from fastapi import APIRouter

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.products import BehaviorRequest
import structlog

router = APIRouter()
logger = structlog.get_logger()


@router.post("/behavior")
async def report_behavior(req: BehaviorRequest):
    """上报用户行为（view/click/purchase）"""
    logger.info(
        "behavior_reported",
        user_id=req.user_id,
        asin=req.asin,
        action=req.action_type,
    )
    return {"status": "ok", "message": f"行为 {req.action_type} 已记录"}
