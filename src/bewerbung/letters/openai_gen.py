"""Anschreiben über die OpenAI-API (Chat Completions, GPT-Modelle)."""

from __future__ import annotations

import logging

import httpx

from bewerbung.letters.base import GeneratedLetter, GenerationError, LetterContext
from bewerbung.letters.http_base import post_json
from bewerbung.letters.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIGenerator:
    name = "openai"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._timeout = timeout
        self._client = client

    @property
    def unavailable_reason(self) -> str | None:
        if not self._api_key:
            return "Kein API-Key (OPENAI_API_KEY in .env eintragen)"
        return None

    def generate(self, ctx: LetterContext) -> GeneratedLetter:
        if reason := self.unavailable_reason:
            raise GenerationError(reason)
        data = post_json(
            self._client,
            label="OpenAI-API",
            url=OPENAI_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            payload={
                "model": self.model,
                # Neuere GPT-Modelle akzeptieren nur noch max_completion_tokens (inkl. Reasoning).
                "max_completion_tokens": 8000,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(ctx)},
                ],
            },
            timeout=self._timeout,
        )
        choices = data.get("choices") or []
        if not choices:
            raise GenerationError("Kein Text erhalten, bitte erneut versuchen")
        choice = choices[0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise GenerationError("Die Anfrage wurde abgelehnt, bitte Hinweise anpassen")
        text = (message.get("content") or "").strip()
        if choice.get("finish_reason") == "length" or not text:
            raise GenerationError("Kein vollständiger Text erhalten, bitte erneut versuchen")
        usage = data.get("usage") or {}
        return GeneratedLetter(
            body=text,
            generator=self.name,
            model=data.get("model") or self.model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
