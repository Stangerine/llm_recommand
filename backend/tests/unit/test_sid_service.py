import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from services.sid_service import SIDService


@pytest.fixture
def sid_service():
    svc = SIDService()
    svc.asin2sid = {"B001": "1_2_3_4", "B002": "5_6_7_8"}
    svc.sid2asin = {"1_2_3_4": "B001", "5_6_7_8": "B002"}
    return svc


def test_asin_to_sid(sid_service):
    assert sid_service.asin_to_sid("B001") == "1_2_3_4"


def test_invalid_asin_returns_none(sid_service):
    assert sid_service.asin_to_sid("B999") is None


def test_batch_filters_invalid(sid_service):
    result = sid_service.asins_to_sids(["B001", "B999", "B002"])
    assert result == ["1_2_3_4", "5_6_7_8"]


def test_sids_to_asins(sid_service):
    result = sid_service.sids_to_asins(["1_2_3_4", "5_6_7_8"])
    assert result == ["B001", "B002"]


def test_sids_to_asins_filters_invalid(sid_service):
    result = sid_service.sids_to_asins(["1_2_3_4", "9_9_9_9", "5_6_7_8"])
    assert result == ["B001", "B002"]


def test_is_valid_sid(sid_service):
    assert sid_service.is_valid_sid("1_2_3_4") is True
    assert sid_service.is_valid_sid("9_9_9_9") is False
