"""
LLMClient — thin wrapper around openai.AsyncOpenAI.

All agents call this; never the SDK directly.
Supports JSON-structured responses with Pydantic validation and retry,
and plain-text responses for full-file generation.

Provider configuration via environment:
  LLM_API_KEY   — OpenAI API key (or compatible)
  LLM_MODEL     — model name, e.g. gpt-4o-mini
  LLM_BASE_URL  — optional; leave empty for OpenAI, set for Ollama
"""
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM call fails after all retries."""


class LLMClient:
    """
    Thin async wrapper around openai.AsyncOpenAI.

    Phase 1: constructor and method signatures implemented.
    Actual LLM calls will be exercised from Phase 2 onwards.
    """

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            # Pass base_url only when explicitly set; None uses the OpenAI default.
            base_url=base_url if base_url else None,
        )
        self.model = model
        self.max_retries = 3

    async def call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel] | None = None,
    ) -> dict[str, Any] | BaseModel:
        """
        Call the LLM and return a validated JSON object.

        Retries up to max_retries on JSON parse or Pydantic validation failure,
        feeding the error back into the prompt on each retry.
        """
        current_user_prompt = user_prompt

        for attempt in range(self.max_retries):
            try:
                response = await self._client.chat.completions.create(
                    model=self.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": current_user_prompt},
                    ],
                )
                raw = response.choices[0].message.content or ""
                logger.debug("LLM raw response (attempt %d): %.200s", attempt + 1, raw)

                data = json.loads(raw)
                if response_model is not None:
                    return response_model.model_validate(data)
                return data

            except (json.JSONDecodeError, ValidationError) as exc:
                if attempt == self.max_retries - 1:
                    raise LLMError(
                        f"LLM returned invalid JSON/schema after {self.max_retries} attempts"
                    ) from exc
                logger.warning(
                    "LLM parse error on attempt %d/%d: %s — retrying",
                    attempt + 1,
                    self.max_retries,
                    exc,
                )
                current_user_prompt = (
                    f"{user_prompt}\n\nPrevious attempt failed with error:\n{exc}\n"
                    "Please return valid JSON that matches the required schema."
                )

        # Should not be reached, but satisfies type checker
        raise LLMError("Unexpected exit from retry loop")

    async def call_text(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call the LLM and return raw text.

        Used by ImplementerAgent (Phase 3) for full-file content generation.
        """
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""


def create_llm_client() -> LLMClient:
    """
    Factory that creates an LLMClient from application settings.
    Imported and called by agents in Phase 2+.
    """
    from devforge.config import settings
    return LLMClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url if settings.llm_base_url else None,
    )
