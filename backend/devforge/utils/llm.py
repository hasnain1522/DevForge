"""Provider fallback kept behind the existing OpenAI-compatible LLMClient."""
import json
import logging
import asyncio
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when no configured provider can return a usable response."""


@dataclass
class _Provider:
    name: str
    model: str
    client: AsyncOpenAI


class LLMClient:
    """Call the preferred provider and fall back without exposing provider errors."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        *,
        providers: list[tuple[str, str, str, str | None]] | None = None,
    ) -> None:
        """Accept legacy single-provider args or ordered (name,key,model,url) providers."""
        self._providers: list[_Provider] = []
        definitions = providers or ([
            ("openai", api_key or "", model, base_url),
        ] if api_key else [])
        for name, key, provider_model, provider_url in definitions:
            if not key:
                continue
            headers = {"HTTP-Referer": "https://devforge.local", "X-Title": "DevForge"} \
                if name == "openrouter" else None
            client = AsyncOpenAI(
                api_key=key,
                base_url=provider_url or None,
                default_headers=headers,
                max_retries=0,
            )
            self._providers.append(_Provider(name, provider_model, client))
        self.max_retries = 3

    async def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> dict[str, Any] | BaseModel:
        for provider in self._providers:
            current_prompt = user_prompt
            for attempt in range(self.max_retries):
                try:
                    response = await provider.client.chat.completions.create(
                        model=provider.model,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": current_prompt},
                        ],
                    )
                    raw = response.choices[0].message.content or ""
                    data = json.loads(raw)
                    return response_model.model_validate(data) if response_model else data
                except (json.JSONDecodeError, ValidationError):
                    if attempt + 1 < self.max_retries:
                        current_prompt = (
                            f"{user_prompt}\n\nReturn valid JSON matching the required schema."
                        )
                    else:
                        break
                except Exception as exc:  # noqa: BLE001 - providers expose multiple exception types
                    logger.warning("LLM provider %s failed (%s); trying fallback", provider.name,
                                   type(exc).__name__)
                    break
        if not self._providers:
            raise LLMError("No LLM provider is configured")
        raise LLMError("Configured LLM providers could not return valid JSON")

    async def call_text(self, system_prompt: str, user_prompt: str) -> str:
        for provider in self._providers:
            current_prompt = user_prompt
            for attempt in range(self.max_retries):
                try:
                    response = await provider.client.chat.completions.create(
                        model=provider.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": current_prompt},
                        ],
                    )
                    content = response.choices[0].message.content
                    if content:
                        return content.strip()
                    logger.warning(
                        "LLM provider %s returned empty text on attempt %d/%d",
                        provider.name, attempt + 1, self.max_retries,
                    )
                except Exception as exc:  # noqa: BLE001 - providers expose multiple exception types
                    logger.warning(
                        "LLM provider %s failed on attempt %d/%d (%s)",
                        provider.name, attempt + 1, self.max_retries, type(exc).__name__,
                    )
                if attempt + 1 < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    current_prompt = (
                        f"{user_prompt}\n\n"
                        "Return only the complete updated file contents. "
                        "Do not use markdown fences."
                    )
            logger.warning("LLM provider %s exhausted text retries; trying fallback", provider.name)
        if not self._providers:
            raise LLMError("No LLM provider is configured")
        raise LLMError("Configured LLM providers could not return text")


def create_llm_client() -> LLMClient:
    """Build provider order from settings; agents remain provider agnostic."""
    from devforge.config import settings

    openai_provider = (
        "openai", settings.llm_api_key if settings.llm_api_key != "not-configured" else "",
        settings.llm_model, settings.llm_base_url or None,
    )
    openrouter_provider = (
        "openrouter", settings.openrouter_api_key, settings.openrouter_model or settings.llm_model,
        settings.openrouter_base_url or "https://openrouter.ai/api/v1",
    )
    providers = [openrouter_provider, openai_provider] if settings.llm_provider == "openrouter" \
        else [openai_provider, openrouter_provider]
    return LLMClient(providers=providers)
