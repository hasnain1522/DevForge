"""Provider selection and fallback tests without live credentials or network calls."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from devforge.config import settings
from devforge.utils.llm import LLMClient, LLMError, create_llm_client


def _response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _client() -> LLMClient:
    return LLMClient(providers=[
        ("openai", "test-openai-key", "test-model", None),
        ("openrouter", "test-openrouter-key", "router-model", "https://openrouter.ai/api/v1"),
    ])


def test_openai_provider_returns_json_without_using_fallback():
    client = _client()
    openai_call = AsyncMock(return_value=_response('{"answer": 42}'))
    router_call = AsyncMock(return_value=_response('{"answer": 0}'))
    client._providers[0].client.chat.completions.create = openai_call
    client._providers[1].client.chat.completions.create = router_call

    result = asyncio.run(client.call_json("system", "user"))
    assert result == {"answer": 42}
    openai_call.assert_awaited_once()
    router_call.assert_not_awaited()


def test_openrouter_is_used_when_openai_request_fails():
    client = _client()
    client._providers[0].client.chat.completions.create = AsyncMock(
        side_effect=RuntimeError("provider unavailable")
    )
    router_call = AsyncMock(return_value=_response("updated file content"))
    client._providers[1].client.chat.completions.create = router_call

    result = asyncio.run(client.call_text("system", "user"))
    assert result == "updated file content"
    router_call.assert_awaited_once()


def test_no_configured_provider_fails_safely():
    async def run():
        return await LLMClient().call_text("system", "user")

    with pytest.raises(LLMError, match="No LLM provider is configured"):
        asyncio.run(run())


def test_factory_orders_openai_and_openrouter_fallback(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", "test-openai-key")
    monkeypatch.setattr(settings, "llm_model", "gpt-test")
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "test-router-key")
    monkeypatch.setattr(settings, "openrouter_model", "router-test")
    client = create_llm_client()
    assert [provider.name for provider in client._providers] == ["openai", "openrouter"]
    assert [provider.model for provider in client._providers] == ["gpt-test", "router-test"]

def test_call_text_retries_before_fallback():
    client = _client()
    openai_call = AsyncMock(
        side_effect=[RuntimeError("temporary"), RuntimeError("temporary"), _response("updated")]
    )
    router_call = AsyncMock(return_value=_response("fallback"))
    client._providers[0].client.chat.completions.create = openai_call
    client._providers[1].client.chat.completions.create = router_call

    result = asyncio.run(client.call_text("system", "user"))
    assert result == "updated"
    assert openai_call.await_count == 3
    router_call.assert_not_awaited()


def test_call_text_falls_back_after_retries():
    client = _client()
    openai_call = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    router_call = AsyncMock(return_value=_response("fallback"))
    client._providers[0].client.chat.completions.create = openai_call
    client._providers[1].client.chat.completions.create = router_call

    result = asyncio.run(client.call_text("system", "user"))
    assert result == "fallback"
    assert openai_call.await_count == 3
    router_call.assert_awaited_once()

