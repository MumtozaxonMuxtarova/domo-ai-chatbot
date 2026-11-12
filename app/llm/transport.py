"""Small Groq HTTP adapter. No SDK, retries, tools, logging or implicit live calls."""

import asyncio
import math

import httpx

from app.llm.errors import LLMConfigurationError, LLMServiceError
from app.llm.prompts import RESPONSE_FORMAT
from app.llm.settings import LLMSettings

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
MAX_RESPONSE_BYTES = 65_536


class GroqClient:
    def __init__(
        self, settings: LLMSettings, *, transport: httpx.AsyncBaseTransport | None = None,
        allow_live_api: bool = False,
    ):
        if not isinstance(allow_live_api, bool):
            raise LLMConfigurationError("allow_live_api faqat True yoki False bo'lishi kerak.")
        if not allow_live_api and not isinstance(transport, httpx.MockTransport):
            raise LLMConfigurationError("Haqiqiy Groq chaqiruvi uchun alohida ruxsat kerak.")
        self.settings = settings
        self._client = httpx.AsyncClient(
            transport=transport, timeout=httpx.Timeout(settings.timeout_seconds),
            follow_redirects=False, trust_env=False,
            headers={"Authorization": "Bearer " + settings.api_key.get_secret_value()},
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    async def aclose(self):
        await self._client.aclose()

    async def complete(self, messages: list[dict]) -> str:
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                async with self._client.stream("POST", ENDPOINT, json={
                    "model": self.settings.model, "messages": messages,
                    "temperature": 0, "max_completion_tokens": self.settings.max_output_tokens,
                    "response_format": RESPONSE_FORMAT, "stream": False,
                }) as response:
                    if response.status_code in (401, 403):
                        raise LLMServiceError("auth_error")
                    if response.status_code == 429:
                        try:
                            retry_after = float(response.headers.get("retry-after", ""))
                            if not math.isfinite(retry_after) or retry_after <= 0:
                                retry_after = None
                            elif retry_after > 300:
                                retry_after = 300.0
                        except ValueError:
                            retry_after = None
                        raise LLMServiceError("rate_limited", retry_after)
                    if response.status_code != 200:
                        raise LLMServiceError("api_error")
                    body = bytearray()
                    async for block in response.aiter_bytes():
                        body.extend(block)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise LLMServiceError("invalid_response")
                    # Parse only after the bounded stream has finished.
                    import json
                    payload = json.loads(body)
                    choice = payload["choices"][0]
                    message = choice["message"]
                    content = message.get("content")
                    if (choice.get("finish_reason") != "stop" or message.get("tool_calls")
                            or message.get("function_call") or not isinstance(content, str)
                            or not content.strip() or len(content) > 16_000):
                        raise LLMServiceError("invalid_response")
                    return content
        except LLMServiceError:
            raise
        except (httpx.TimeoutException, TimeoutError):
            raise LLMServiceError("timeout") from None
        except httpx.RequestError:
            raise LLMServiceError("network_error") from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise LLMServiceError("invalid_response") from None
