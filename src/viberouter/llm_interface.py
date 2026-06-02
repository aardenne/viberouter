"""VibeRouter — Streaming LLM Client with retry logic."""

import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, AsyncIterator
from .config import NodeConfig

logger = logging.getLogger("viberouter")


class LLMClient:
    """Client for making requests to LLM endpoints with streaming and retry support."""

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
        self.max_retries = 3
        self.retry_delay = 1.0

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
        """Send a chat completion request with retry logic."""
        self.request_count += 1
        last_error = None

        for attempt in range(1, self.max_retries + 1):
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
                            error_body = await response.aread()
                            error_msg = f"API error: {response.status_code} - {error_body.decode()[:200]}"
                            raise Exception(error_msg)
            except httpx.ReadTimeout:
                last_error = f"Timeout on attempt {attempt}/{self.max_retries}"
                logger.warning(last_error)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                if "status_code" in str(e):
                    self.error_count += 1
                    raise
                last_error = str(e)
                if attempt < self.max_retries:
                    logger.warning(f"Attempt {attempt}/{self.max_retries} failed: {e}")
                    await asyncio.sleep(self.retry_delay * attempt)

        self.error_count += 1
        raise Exception(f"All {self.max_retries} attempts failed. Last error: {last_error}")

    async def chat_stream(self, messages: list, **kwargs) -> AsyncIterator[str]:
        """Stream a chat completion response with retry logic."""
        self.request_count += 1
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                payload = {
                    "model": self.node.model,
                    "messages": messages,
                    "stream": True,
                    **kwargs,
                }
                async with self.client:
                    async with self.client.stream("POST", "/v1/chat/completions", json=payload) as response:
                        if response.status_code == 200:
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    if data_str.strip() == "[DONE]":
                                        return
                                    import json
                                    try:
                                        data = json.loads(data_str)
                                        content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if content:
                                            yield content
                                    except json.JSONDecodeError:
                                        pass
                            return
                        else:
                            error_msg = f"API error: {response.status_code}"
                            raise Exception(error_msg)
            except httpx.ReadTimeout:
                last_error = f"Timeout on attempt {attempt}/{self.max_retries}"
                logger.warning(last_error)
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
            except Exception as e:
                if "status_code" in str(e):
                    self.error_count += 1
                    raise
                last_error = str(e)
                if attempt < self.max_retries:
                    logger.warning(f"Attempt {attempt}/{self.max_retries} failed: {e}")
                    await asyncio.sleep(self.retry_delay * attempt)

        self.error_count += 1
        raise Exception(f"All {self.max_retries} attempts failed. Last error: {last_error}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
