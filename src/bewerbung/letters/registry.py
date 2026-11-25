"""Verfügbare Generatoren aus der Konfiguration bauen."""

from __future__ import annotations

from bewerbung.config import Settings
from bewerbung.letters.base import LetterGenerator
from bewerbung.letters.claude import ClaudeGenerator
from bewerbung.letters.gemini import GeminiGenerator
from bewerbung.letters.openai_gen import OpenAIGenerator
from bewerbung.letters.template import TemplateGenerator


def build_generators(settings: Settings) -> dict[str, LetterGenerator]:
    """Reihenfolge = Priorität bei "auto": der erste Anbieter mit Key, sonst die Vorlage."""
    timeout = settings.cover_letter_timeout
    return {
        "claude": ClaudeGenerator(settings.anthropic_api_key, settings.cover_letter_model, timeout),
        "openai": OpenAIGenerator(settings.openai_api_key, settings.openai_model, timeout),
        "gemini": GeminiGenerator(settings.gemini_api_key, settings.gemini_model, timeout),
        "template": TemplateGenerator(),
    }
