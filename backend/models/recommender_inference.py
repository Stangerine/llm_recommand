import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

# 尝试导入 torch，如果失败则使用模拟模式
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class RecommenderInference:
    """单例，服务启动时加载一次，避免重复初始化开销。"""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.use_simulation = not TORCH_AVAILABLE

    def load(self, valid_sids: list[str]):
        """加载推荐模型"""
        if not TORCH_AVAILABLE:
            print(f"[WARN] PyTorch 未安装，使用模拟模式 | 合法SID数: {len(valid_sids)}")
            return

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(settings.model_base)
            base = AutoModelForCausalLM.from_pretrained(
                settings.model_base,
                torch_dtype=torch.float16,
                device_map=settings.model_device,
            )
            self.model = PeftModel.from_pretrained(base, settings.model_lora_path)
            self.model.eval()
            print(f"[OK] 推荐模型就绪 | 合法SID数: {len(valid_sids)}")
        except Exception as e:
            print(f"[WARN] 模型加载失败: {e}，使用模拟模式")
            self.model = None
            self.tokenizer = None

    def _build_prompt(self, history_sids: list[str]) -> str:
        """构建推荐 prompt"""
        return (
            "[INST] Based on the user's browsing history (item semantic IDs):\n"
            f"History: {' '.join(history_sids)}\n"
            "Predict the next items. Output semantic IDs only, one per line.\n[/INST]"
        )

    def predict(self, history_sids: list[str]) -> list[str]:
        """预测候选 SID 列表"""
        if self.model is None:
            # 模拟模式：返回确定性随机 SID
            import random
            random.seed(hash(tuple(history_sids)))
            return [f"{random.randint(0,15)}_{random.randint(0,15)}_{random.randint(0,15)}_{random.randint(0,15)}" for _ in range(settings.top_k)]

        if not TORCH_AVAILABLE:
            # 不应该到达这里，但作为安全措施
            import random
            random.seed(hash(tuple(history_sids)))
            return [f"{random.randint(0,15)}_{random.randint(0,15)}_{random.randint(0,15)}_{random.randint(0,15)}" for _ in range(settings.top_k)]

        # 使用 torch 进行推理
        with torch.inference_mode():
            prompt = self._build_prompt(history_sids)
            inputs = self.tokenizer(prompt, return_tensors="pt").to(settings.model_device)

            outputs = self.model.generate(
                **inputs,
                num_beams=settings.beam_search_num_beams,
                num_return_sequences=settings.beam_search_num_beams,
                max_new_tokens=32,
                early_stopping=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

            candidates, seen = [], set()
            for output in outputs:
                generated = output[inputs["input_ids"].shape[1] :]
                sid = (
                    self.tokenizer.decode(generated, skip_special_tokens=True)
                    .strip()
                    .split("\n")[0]
                    .strip()
                )
                if sid and sid not in seen:
                    seen.add(sid)
                    candidates.append(sid)
                if len(candidates) >= settings.top_k:
                    break

            return candidates
