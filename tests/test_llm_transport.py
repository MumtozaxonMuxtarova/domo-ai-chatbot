"""Groq HTTP contracts through httpx.MockTransport; no live credentials or network."""

import json

import httpx
import pytest
from pydantic import SecretStr

from app.llm.errors import LLMConfigurationError, LLMServiceError
from app.llm.prompts import RESPONSE_FORMAT
from app.llm.settings import LLMSettings
from app.llm.transport import GroqClient

FAKE_KEY = "gsk_offline_test_key_never_sent_to_a_server"
PRIVATE_TEXT = "private-user-question-must-not-appear-in-errors"
CONTENT = json.dumps({"answerable": False, "answer": "", "document_ids": [], "evidence": []})
MESSAGES = [{"role": "system", "content": "Use supplied evidence only."},
            {"role": "user", "content": PRIVATE_TEXT}]


@pytest.fixture
def settings():
    return LLMSettings(
        api_key=SecretStr(FAKE_KEY), model="openai/gpt-oss-20b",
        timeout_seconds=7.5, max_output_tokens=256,
    )


def successful_response(content=CONTENT):
    return {"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content}}]}


async def test_mock_request_uses_fixed_endpoint_config_and_strict_schema_and_closes(settings):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer " + FAKE_KEY
        payload = json.loads(request.content)
        assert payload["model"] == settings.model
        assert payload["messages"] == MESSAGES
        assert payload["temperature"] == 0
        assert payload["response_format"] == RESPONSE_FORMAT
        assert payload.get("max_completion_tokens", payload.get("max_tokens")) == 256
        assert payload.get("stream", False) is False
        assert all(value == 7.5 for value in request.extensions["timeout"].values())
        return httpx.Response(200, json=successful_response())

    class RecordingMockTransport(httpx.MockTransport):
        closed = False

        async def aclose(self):
            self.closed = True
            await super().aclose()

    transport = RecordingMockTransport(handler)
    async with GroqClient(settings, transport=transport) as client:
        assert await client.complete(MESSAGES) == CONTENT
    assert len(requests) == 1
    assert transport.closed


def test_live_network_requires_explicit_approval(settings):
    with pytest.raises(LLMConfigurationError):
        GroqClient(settings)


@pytest.mark.parametrize("invalid_flag", ["false", "true", 1, 0, None])
def test_live_network_approval_rejects_non_boolean_flags(settings, invalid_flag):
    with pytest.raises(LLMConfigurationError):
        GroqClient(settings, allow_live_api=invalid_flag)


@pytest.mark.parametrize("status,code", [
    (401, "auth_error"), (403, "auth_error"), (429, "rate_limited"),
    (503, "api_error"), (307, "api_error"),
])
async def test_http_errors_are_typed_safe_and_never_retried_or_redirected(settings, status, code, caplog):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, text="private-server-detail " + FAKE_KEY,
            headers={"Location": "https://invalid.example/secret-leak-target"},
        )

    async with GroqClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMServiceError) as error:
            await client.complete(MESSAGES)
    assert error.value.code == code
    assert len(requests) == 1
    for secret in (FAKE_KEY, PRIVATE_TEXT, "private-server-detail"):
        assert secret not in str(error.value)
        assert secret not in repr(error.value)
        assert secret not in caplog.text


async def test_rate_limit_retry_after_accepts_only_positive_bounded_seconds(settings):
    for raw, expected in (("12", 12.0), ("900", 300.0), ("-1", None),
                          ("0", None), ("not-a-number", None)):
        def handler(request, value=raw):
            return httpx.Response(429, headers={"Retry-After": value})
        async with GroqClient(settings, transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(LLMServiceError) as error:
                await client.complete(MESSAGES)
        assert error.value.code == "rate_limited"
        assert error.value.retry_after == expected


@pytest.mark.parametrize("exception,code", [
    (httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "network_error"),
])
async def test_timeout_and_network_failures_hide_internal_messages(settings, exception, code):
    requests = []

    def handler(request):
        requests.append(request)
        raise exception("private-transport-detail " + FAKE_KEY, request=request)

    async with GroqClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMServiceError) as error:
            await client.complete(MESSAGES)
    assert error.value.code == code
    assert len(requests) == 1
    assert "private-transport-detail" not in str(error.value)
    assert FAKE_KEY not in str(error.value)


@pytest.mark.parametrize("response_kind", ["not_json", "no_choices", "missing_content", "tool_calls", "truncated"])
async def test_malformed_or_unsafe_success_response_is_rejected(settings, response_kind):
    def handler(request):
        if response_kind == "not_json":
            return httpx.Response(200, text="private-malformed-server-response")
        payload = successful_response()
        if response_kind == "no_choices":
            payload = {"choices": []}
        elif response_kind == "missing_content":
            payload["choices"][0]["message"].pop("content")
        elif response_kind == "tool_calls":
            payload["choices"][0]["message"]["tool_calls"] = [{"id": "not-authorized"}]
        else:
            payload["choices"][0]["finish_reason"] = "length"
        return httpx.Response(200, json=payload)

    async with GroqClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMServiceError) as error:
            await client.complete(MESSAGES)
    assert error.value.code == "invalid_response"
    assert "private-malformed-server-response" not in str(error.value)


async def test_oversize_response_is_rejected(settings):
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, json=successful_response("x" * 1_100_000),
    ))
    async with GroqClient(settings, transport=transport) as client:
        with pytest.raises(LLMServiceError) as error:
            await client.complete(MESSAGES)
    assert error.value.code == "invalid_response"
