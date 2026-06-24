import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings


class SIDService:
    """
    启动时将全量映射加载至内存（字典查询 < 1ms）。
    Redis 用于跨进程共享与动态更新场景。
    """

    def __init__(self):
        self.asin2sid: dict[str, str] = {}
        self.sid2asin: dict[str, str] = {}

    async def initialize(self):
        with open(settings.sid_mapping_path) as f:
            data = json.load(f)
        self.asin2sid = data["asin2sid"]
        self.sid2asin = data["sid2asin"]
        print(f"[OK] SID 服务就绪: {len(self.asin2sid)} 个商品")

    def asin_to_sid(self, asin: str) -> str | None:
        return self.asin2sid.get(asin)

    def asins_to_sids(self, asins: list[str]) -> list[str]:
        return [s for a in asins if (s := self.asin2sid.get(a))]

    def sids_to_asins(self, sids: list[str]) -> list[str]:
        return [a for s in sids if (a := self.sid2asin.get(s))]

    def is_valid_sid(self, sid: str) -> bool:
        return sid in self.sid2asin
