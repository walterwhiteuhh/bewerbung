from __future__ import annotations

from bewerbung.config import Settings
from bewerbung.search.adzuna import AdzunaProvider
from bewerbung.search.arbeitsagentur import ArbeitsagenturProvider
from bewerbung.search.base import SearchProvider


def build_providers(settings: Settings) -> list[SearchProvider]:
    return [
        ArbeitsagenturProvider(settings.arbeitsagentur_api_key, settings.search_timeout),
        AdzunaProvider(settings.adzuna_app_id, settings.adzuna_app_key, settings.search_timeout),
    ]
