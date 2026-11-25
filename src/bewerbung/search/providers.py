from __future__ import annotations

from bewerbung.config import Settings
from bewerbung.search.adzuna import AdzunaProvider
from bewerbung.search.arbeitnow import ArbeitnowProvider
from bewerbung.search.arbeitsagentur import ArbeitsagenturProvider
from bewerbung.search.base import SearchProvider
from bewerbung.search.jooble import JoobleProvider
from bewerbung.search.remotive import RemotiveProvider


def build_providers(settings: Settings) -> list[SearchProvider]:
    return [
        ArbeitsagenturProvider(settings.arbeitsagentur_api_key, settings.search_timeout),
        AdzunaProvider(settings.adzuna_app_id, settings.adzuna_app_key, settings.search_timeout),
        JoobleProvider(settings.jooble_api_key, settings.search_timeout, settings.jooble_base_url),
        ArbeitnowProvider(settings.search_timeout),
        RemotiveProvider(settings.search_timeout),
    ]
