"""LLM Client wrapper for OpenAI-compatible APIs."""

import httpx
import asyncio
from typing import Optional, Dict, Any
from .config import NodeConfig


class LLMClient:
    """Client for making requests to LLM endpoints."""

    def __init__(self, node: NodeConfig):
        self.node = node
        self.client = httpx.AsyncClient(
            base_url=node.url,
            timeout=node.timeout,
            headers={"Authorization": f"Bearer {node.api_key}"} if node.api_key else None,
            limits=httpx.Limits(max_connections=node.max_connections),
        )
        self.is_healthy = True
        self.request_count = 0
        self.error_count = 0
        self.total_tokens = 0

    async def health_check(self) -> bool:
        """Check if the node is healthy."""
        try:
            async with self.client:
                async with self.client.stream("GET", "/health") as response:
                    if response.status_code == 200:
                        self.is_healthy = True
                        return True
                    else:
                        self.is_healthy = False
                        return False
        except Exception:
            self.is_healthy = False
            return False

    async def chat(self, messages: list, **kwargs) -> Dict[str, Any]:
        """Send a chat completion request."""
        self.request_count += 1
        try:
            payload = {
                "model": self.node.model,
                "messages": messages,
                **kwargs,
            }
            async with self.client:
                async with self.client.stream("POST", "/v1/chat/completions", json=payload) as response:
                    if response.status_code == 200:
                        data = await response.aread()
                        import json
                        result = json.loads(data)
                        self.total_tokens += result.get("usage", {}).get("total_tokens", 0)
                        return result
                    else:
                        self.error_count += 1
                        raise Exception(f"API error: {response.status_code}")
        except Exception as e:
            self.error_count += 1
            raise e

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
