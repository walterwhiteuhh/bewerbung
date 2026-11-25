"""Ortsangaben und Koordinaten aus Rohdaten, Entfernungen (ohne Geocoding-Dienst).

Koordinaten kommen nur aus den Quellen selbst (Arbeitsagentur-Lokationen, JSON-LD
``jobLocation.geo``). Der Wohnort wird über bereits bekannte Orte mit Koordinaten
aufgelöst; so verlässt keine Adresse die App.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

EARTH_RADIUS_KM = 6371.0
_PLZ = re.compile(r"\b(\d{5})\b")
_LAT_KEYS = ("lat", "latitude", "breite", "breitengrad")
_LON_KEYS = ("lon", "lng", "longitude", "laenge", "länge", "laengengrad")


@dataclass(frozen=True, slots=True)
class Place:
    city: str | None = None
    postal_code: str | None = None
    region: str | None = None
    lat: float | None = None
    lon: float | None = None

    @property
    def has_coords(self) -> bool:
        return self.lat is not None and self.lon is not None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a)), 1)


def _num(value: Any) -> float | None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return num if math.isfinite(num) else None


def _coords(node: Any, depth: int = 0) -> tuple[float, float] | None:
    """Sucht lat/lon-Paare in beliebig verschachtelten Objekten (max. 3 Ebenen)."""
    if not isinstance(node, dict) or depth > 3:
        return None
    lower = {str(k).casefold(): v for k, v in node.items()}
    lat = next((_num(lower[k]) for k in _LAT_KEYS if k in lower), None)
    lon = next((_num(lower[k]) for k in _LON_KEYS if k in lower), None)
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    for value in node.values():
        if isinstance(value, dict) and (found := _coords(value, depth + 1)):
            return found
    return None


def _clean(value: Any) -> str | None:
    if isinstance(value, str | int) and str(value).strip():
        return str(value).strip()
    return None


def _aa_place(item: dict[str, Any]) -> Place | None:
    lokationen = item.get("stellenlokationen")
    node = lokationen[0] if isinstance(lokationen, list) and lokationen else item.get("arbeitsort")
    if not isinstance(node, dict):
        return None
    raw_address = node.get("adresse")
    address: dict[str, Any] = raw_address if isinstance(raw_address, dict) else node
    coords = _coords(node)
    region = _clean(address.get("region"))
    return Place(
        city=_clean(address.get("ort")),
        postal_code=_clean(address.get("plz")),
        region=region.title() if region and region.isupper() else region,
        lat=coords[0] if coords else None,
        lon=coords[1] if coords else None,
    )


def _json_ld_place(node: dict[str, Any]) -> Place | None:
    places = node.get("jobLocation")
    first = places[0] if isinstance(places, list) and places else places
    if not isinstance(first, dict):
        return None
    raw_address = first.get("address")
    address: dict[str, Any] = raw_address if isinstance(raw_address, dict) else {}
    coords = _coords(first.get("geo")) or _coords(first)
    return Place(
        city=_clean(address.get("addressLocality")),
        postal_code=_clean(address.get("postalCode")),
        region=_clean(address.get("addressRegion")),
        lat=coords[0] if coords else None,
        lon=coords[1] if coords else None,
    )


def place_from_payload(raw: Any, location_text: str | None = None) -> Place:
    """Bestmögliche Ortsangabe aus Rohdaten; Rückfall: Freitext 'PLZ Ort, Region'."""
    if isinstance(raw, dict):
        if isinstance(raw.get("source_payload"), dict):
            raw = raw["source_payload"]
        found = None
        if "stellenlokationen" in raw or "arbeitsort" in raw:
            found = _aa_place(raw)
        elif isinstance(raw.get("json_ld"), dict):
            found = _json_ld_place(raw["json_ld"])
        if found is not None and (found.city or found.has_coords):
            return found
    return place_from_text(location_text)


def place_from_text(text: str | None) -> Place:
    if not text or not text.strip():
        return Place()
    plz = _PLZ.search(text)
    head = re.split(r"[,(/;]", _PLZ.sub(" ", text), maxsplit=1)[0]
    city = " ".join(head.split()) or None
    if city and re.fullmatch(r"(?i)remote.*|home\s*office|deutschlandweit|bundesweit", city):
        city = None
    return Place(city=city, postal_code=plz.group(1) if plz else None)


def city_key(city: str | None) -> str | None:
    """'Hamburg-Altona' und 'hamburg' -> 'hamburg' (Stadtteile fallen auf die Stadt)."""
    if not city:
        return None
    key = re.split(r"[-/(,]", city.casefold(), maxsplit=1)[0].strip()
    return re.sub(r"\s+", " ", key) or None
