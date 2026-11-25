"""Firmen-Websites normalisieren und aus Anzeigen-Rohdaten ableiten (ohne Netzwerk)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

# Hosts von Jobportalen und Bewerbermanagement-Systemen sind keine Firmen-Websites.
_PORTAL_SUFFIXES = (
    "arbeitsagentur.de",
    "stepstone.de",
    "stepstone.com",
    "xing.com",
    "linkedin.com",
    "indeed.com",
    "indeed.de",
    "glassdoor.de",
    "glassdoor.com",
    "monster.de",
    "jobware.de",
    "kununu.com",
    "personio.de",
    "personio.com",
    "greenhouse.io",
    "lever.co",
    "softgarden.io",
    "softgarden.de",
    "join.com",
    "myworkdayjobs.com",
    "workday.com",
    "smartrecruiters.com",
    "successfactors.com",
    "successfactors.eu",
    "recruitee.com",
    "jobs.ashbyhq.com",
    "remotive.com",
    "arbeitnow.com",
    "jooble.org",
    "adzuna.de",
    "adzuna.com",
    # Soziale Netzwerke: werden als Profile erfasst (domain/socials.py), nicht als Website.
    "instagram.com",
    "facebook.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "github.com",
)


def normalize_website(value: str | None) -> str | None:
    """'acme.de/' -> 'https://acme.de'. Ungültiges wird zu None."""
    if not value or not value.strip():
        return None
    raw = value.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname or "." not in parts.hostname:
        return None
    host = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, host, path, "", ""))


def is_portal_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == s or host.endswith(f".{s}") for s in _PORTAL_SUFFIXES)


def website_from_payload(raw: Any) -> str | None:
    """``hiringOrganization.sameAs``/``url`` aus JSON-LD, sofern es keine Portal-Adresse ist."""
    if not isinstance(raw, dict):
        return None
    node = raw.get("json_ld") if isinstance(raw.get("json_ld"), dict) else raw
    org = node.get("hiringOrganization") if isinstance(node, dict) else None
    if isinstance(org, list):
        org = org[0] if org else None
    if not isinstance(org, dict):
        return None
    for key in ("sameAs", "url"):
        values = org.get(key)
        for value in values if isinstance(values, list) else [values]:
            site = normalize_website(value) if isinstance(value, str) else None
            if site and not is_portal_host(site):
                return site
    return None
