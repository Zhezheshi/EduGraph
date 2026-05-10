import httpx
import json
import logging
from .config import settings

logger = logging.getLogger(__name__)

THINKING_CONFIG = {
    "extraction": False,
    "alignment": True,
    "integration": True,
    "rag_qa": False,
    "dialogue": False,
}


class LLMClient:
    def __init__(self):
        self.api_key = settings.dashscope_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.embedding_model = settings.embedding_model
        self.token_usage = {"prompt": 0, "completion": 0, "total": 0}

    async def chat(self, messages, json_mode=False, thinking=None, max_tokens=None):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens or 4000}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if thinking is not None:
            payload["enable_thinking"] = thinking

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        self.token_usage["prompt"] += usage.get("prompt_tokens", 0)
        self.token_usage["completion"] += usage.get("completion_tokens", 0)
        self.token_usage["total"] += usage.get("total_tokens", 0)

        return data["choices"][0]["message"]["content"]

    async def chat_json(self, system_prompt, user_prompt, thinking=None, max_tokens=None):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        raw = await self.chat(messages, json_mode=True, thinking=thinking, max_tokens=max_tokens)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)

    async def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.embedding_model, "input": texts, "dimensions": 1024}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return [d["embedding"] for d in data["data"]]

    def get_token_usage(self):
        return self.token_usage.copy()


llm_client = LLMClient()
