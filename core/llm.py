# IdleAgent v0.6.0 - core/llm.py
# LLM 客户端：DeepSeek / OpenAI 兼容接口（httpx 实现，无 SDK 依赖）

import os
import json
from typing import List, Dict, Any, Optional


class LLMClient:
    """极简的 OpenAI 兼容 Chat Completions 客户端。

    通过环境变量配置:
        LLM_PROVIDER      deepseek | openai | 自定义
        LLM_API_KEY       API 密钥
        LLM_BASE_URL      接口地址（默认 DeepSeek）
        LLM_MODEL         模型名（默认 deepseek-chat）
        LLM_TEMPERATURE   采样温度
    """

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or os.environ.get('LLM_API_KEY', '')
        self.model = model or os.environ.get('LLM_MODEL', 'deepseek-chat')
        self.temperature = float(os.environ.get('LLM_TEMPERATURE', '0.3'))
        self.base_url = (
            base_url or os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com')
        ).rstrip('/')
        # token 消耗统计（累计）
        self.usage = {
            'calls': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'cached_tokens': 0,
        }

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def chat(self, messages: List[Dict[str, str]], temperature: float = None) -> str:
        """调用 Chat Completions，返回 assistant 文本内容。"""
        import httpx

        if not self.api_key:
            raise RuntimeError('LLM_API_KEY 未配置，无法调用 LLM')

        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature if temperature is None else temperature,
        }
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        url = f'{self.base_url}/chat/completions'

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 累计 token 消耗
        u = data.get('usage') or {}
        self.usage['calls'] += 1
        self.usage['prompt_tokens'] += int(u.get('prompt_tokens', 0))
        self.usage['completion_tokens'] += int(u.get('completion_tokens', 0))
        self.usage['total_tokens'] += int(u.get('total_tokens', 0))
        self.usage['cached_tokens'] += int(
            (u.get('prompt_tokens_details') or {}).get('cached_tokens', 0) or 0
        )

        return data['choices'][0]['message']['content']
