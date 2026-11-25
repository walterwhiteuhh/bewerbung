"""Firmenlogos aus den Rohdaten der Quellen lesen.

Kein Netzwerkzugriff: die Funktion sucht nur in bereits gespeicherten Payloads
(JSON-LD ``hiringOrganization.logo``, Felder der Such-APIs). Dadurch lassen sich auch
alte Datensätze nachträglich auswerten (Migration 0008).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

MAX_URL_LENGTH = 2048

# Feldnamen der Such-APIs (Remotive: company_logo, Arbeitnow/Jooble je nach Version).
_API_KEYS = ("company_logo_url", "company_logo", "logo_url", "logo", "companyLogo")
# Arbeitsagentur: Logos liegen hinter einem Endpunkt mit API-Key -> eigener Proxy.
_AA_HASH_KEYS = ("kundennummerHash", "arbeitgeberHash", "logoHashId")
AA_LOGO_PATH = "/api/logos/arbeitsagentur/{hash}"


def clean_logo_url(value: Any) -> str | None:
    """Nur absolute http(s)-URLs oder der eigene AA-Proxy; data:/javascript: fliegen raus."""
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl") or value.get("@id")
    if isinstance(value, list):
        value = next((v for v in value if clean_logo_url(v)), None)
        return clean_logo_url(value)
    if not isinstance(value, str):
        return None
    url = value.strip()
    if url.startswith("//"):
        url = f"https:{url}"
    if len(url) > MAX_URL_LENGTH:
        return None
    if url.startswith(("https://", "http://")) or url.startswith("/api/logos/"):
        return url
    return None


def aa_logo_url(item: dict[str, Any]) -> str | None:
    # Feldname je nach API-Version unterschiedlich; unbekannte "...logo..."-Hashes mitnehmen.
    keys = [*_AA_HASH_KEYS, *(k for k in item if "logo" in k.lower() and k not in _AA_HASH_KEYS)]
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip() and value.strip().isascii():
            value = value.strip()
            if value.startswith(("http://", "https://")):
                return clean_logo_url(value)
            return AA_LOGO_PATH.format(hash=quote(value, safe=""))
    return None


def _from_json_ld(node: Any) -> str | None:
    if not isinstance(node, dict):
        return None
    org = node.get("hiringOrganization")
    if isinstance(org, list):
        org = org[0] if org else None
    if isinstance(org, dict):
        return clean_logo_url(org.get("logo")) or clean_logo_url(org.get("image"))
    return None


def logo_from_payload(raw: Any, *, depth: int = 0) -> str | None:
    """Logo-URL aus einem Rohdaten-Objekt (Listing, Import oder gemerkter Treffer)."""
    if not isinstance(raw, dict) or depth > 3:
        return None
    if (url := _from_json_ld(raw.get("json_ld"))) is not None:
        return url
    if (url := _from_json_ld(raw)) is not None:  # Roh-JSON-LD ohne Hülle
        return url
    for key in _API_KEYS:
        if (url := clean_logo_url(raw.get(key))) is not None:
            return url
    if isinstance(raw.get("referenznummer") or raw.get("refnr"), str):
        return aa_logo_url(raw)
    # Gemerkter Suchtreffer: {"listing_id": ..., "source_payload": {...}}
    return logo_from_payload(raw.get("source_payload"), depth=depth + 1)
