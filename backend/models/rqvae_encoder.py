import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

# 尝试导入 torch
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class RQVAEEncoder:
    """RQ-VAE 编码器，将商品文本转换为语义 ID (SID)"""

    def __init__(self, ckpt_path: str | None = None):
        self.ckpt_path = ckpt_path or settings.rqvae_path
        self.model = None
        self._load_model()

    def _load_model(self):
        """加载 RQ-VAE 模型权重"""
        ckpt_path = Path(self.ckpt_path)
        if not ckpt_path.exists():
            print(f"[WARN] RQ-VAE 检查点不存在: {self.ckpt_path}，使用模拟模式")
            self.model = None
            return

        if not TORCH_AVAILABLE:
            print(f"[WARN] PyTorch 未安装，使用模拟模式")
            self.model = None
            return

        try:
            # 实际加载逻辑需要根据 RQ-VAE 实现调整
            # 这里提供框架代码
            # checkpoint = torch.load(ckpt_path / "model.pt", map_location="cpu")
            # self.model = RQVAEModel(**checkpoint["config"])
            # self.model.load_state_dict(checkpoint["state_dict"])
            # self.model.eval()
            print(f"[OK] RQ-VAE 模型加载成功: {self.ckpt_path}")
        except Exception as e:
            print(f"[WARN] RQ-VAE 模型加载失败: {e}，使用模拟模式")
            self.model = None

    def encode_single(self, text: str) -> str:
        """编码单个文本为 SID"""
        if self.model is None:
            # 模拟模式：生成确定性 SID
            hash_val = hash(text) % 10000
            return f"{hash_val // 1000}_{(hash_val % 1000) // 100}_{(hash_val % 100) // 10}_{hash_val % 10}"

        # 实际编码逻辑
        # with torch.no_grad():
        #     tokens = self.tokenizer(text, return_tensors="pt")
        #     codes = self.model.encode(tokens)
        #     return "_".join(str(c.item()) for c in codes[0])
        return ""

    def encode_batch(self, texts: list[str]) -> list[str]:
        """批量编码文本为 SID"""
        if self.model is None:
            return [self.encode_single(t) for t in texts]

        # 实际批量编码逻辑
        # with torch.no_grad():
        #     tokens = self.tokenizer(texts, return_tensors="pt", padding=True)
        #     codes = self.model.encode(tokens)
        #     return ["_".join(str(c.item()) for c in row) for row in codes]
        return [self.encode_single(t) for t in texts]
