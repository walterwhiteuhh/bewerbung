"""Anschreiben über die Gemini-API (Google AI Studio, generateContent)."""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

from bewerbung.letters.base import GeneratedLetter, GenerationError, LetterContext
from bewerbung.letters.http_base import post_json
from bewerbung.letters.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiGenerator:
    name = "gemini"

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
            return "Kein API-Key (GEMINI_API_KEY in .env eintragen)"
        return None

    def generate(self, ctx: LetterContext) -> GeneratedLetter:
        if reason := self.unavailable_reason:
            raise GenerationError(reason)
        data = post_json(
            self._client,
            label="Gemini-API",
            url=GEMINI_URL.format(model=quote(self.model, safe="")),
            # Key im Header statt in der URL, damit er nicht in Proxy-/Server-Logs landet.
            headers={"x-goog-api-key": self._api_key or ""},
            payload={
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": build_user_prompt(ctx)}]}],
                "generationConfig": {"maxOutputTokens": 8192},
            },
            timeout=self._timeout,
        )
        if (data.get("promptFeedback") or {}).get("blockReason"):
            raise GenerationError("Die Anfrage wurde abgelehnt, bitte Hinweise anpassen")
        candidates = data.get("candidates") or []
        if not candidates:
            raise GenerationError("Kein Text erhalten, bitte erneut versuchen")
        cand = candidates[0]
        finish = cand.get("finishReason")
        if finish in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"}:
            raise GenerationError("Die Anfrage wurde abgelehnt, bitte Hinweise anpassen")
        parts = (cand.get("content") or {}).get("parts") or []
        # Gedanken-Teile (thought=True) gehören nicht ins Anschreiben.
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
        if finish == "MAX_TOKENS" or not text:
            raise GenerationError("Kein vollständiger Text erhalten, bitte erneut versuchen")
        usage = data.get("usageMetadata") or {}
        return GeneratedLetter(
            body=text,
            generator=self.name,
            model=data.get("modelVersion") or self.model,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
        )
