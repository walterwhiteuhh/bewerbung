"""Anschreiben über die Claude-API (Anthropic SDK)."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

from bewerbung.letters.base import GeneratedLetter, GenerationError, LetterContext
from bewerbung.letters.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

# Bei einer Ablehnung durch die Sicherheitsfilter wählt die API selbst ein Ersatzmodell.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeGenerator:
    name = "claude"

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout: float = 120.0,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._api_key = api_key
        # ``client`` erlaubt Tests ohne Netzwerk; sonst wird der SDK-Client erst bei Bedarf gebaut.
        self._client = client
        self._timeout = timeout

    @property
    def unavailable_reason(self) -> str | None:
        if self._client is None and not self._api_key:
            return "Kein API-Key (ANTHROPIC_API_KEY in .env eintragen)"
        return None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=self._api_key, timeout=self._timeout, max_retries=2
            )
        return self._client

    def generate(self, ctx: LetterContext) -> GeneratedLetter:
        if reason := self.unavailable_reason:
            raise GenerationError(reason)
        try:
            response = self._get_client().beta.messages.create(
                model=self.model,
                max_tokens=8000,
                betas=[_FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": "medium"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(ctx)}],
            )
        except anthropic.AuthenticationError as exc:
            raise GenerationError("API-Key ungültig") from exc
        except anthropic.RateLimitError as exc:
            raise GenerationError("Zu viele Anfragen, bitte gleich nochmal versuchen") from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Claude-API Fehler %s: %s", exc.status_code, exc.message)
            raise GenerationError(f"Claude-API Fehler {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise GenerationError("Claude-API nicht erreichbar") from exc

        if response.stop_reason == "refusal":
            raise GenerationError("Die Anfrage wurde abgelehnt, bitte Hinweise anpassen")
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "max_tokens" or not text:
            raise GenerationError("Kein vollständiger Text erhalten, bitte erneut versuchen")
        usage = response.usage
        logger.info(
            "Anschreiben erzeugt (%s, %s in / %s out Tokens)",
            response.model,
            usage.input_tokens,
            usage.output_tokens,
        )
        return GeneratedLetter(
            body=text,
            generator=self.name,
            model=response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
