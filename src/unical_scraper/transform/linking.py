"""Deterministic linking helpers across normalized datasets."""

from __future__ import annotations

import re
from typing import Any


_CUBO_RE = re.compile(r"\bcubo\s*([0-9]{1,2})(?:\s*[/-]?\s*([a-z]))?\b", re.IGNORECASE)
_CUBI_RE = re.compile(r"\bcubo\s*([0-9]{1,2})\s*[/-]\s*([0-9]{1,2}[a-z]?)\b", re.IGNORECASE)
_NON_LINKABLE_PLACE_IDS = {
    "service-miai",
    "service-musnob",
    "service-orto-botanico",
    "service-rimuseum",
    "service-socialita-nel-campus",
    "service-quartieri",
    "service-servizio-mensa",
}


def link_places_to_buildings(
    places: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return places with `building_id` inferred from known building records."""
    building_ids = {
        str(item["building_id"])
        for item in buildings
        if isinstance(item, dict) and item.get("building_id")
    }

    linked: list[dict[str, Any]] = []
    for place in places:
        updated = dict(place)

        existing_building_id = updated.get("building_id")
        if isinstance(existing_building_id, str) and existing_building_id in building_ids:
            linked.append(updated)
            continue

        inferred = _infer_building_id(updated, building_ids)
        if inferred:
            updated["building_id"] = inferred

        linked.append(updated)

    return linked


def _infer_building_id(place: dict[str, Any], known_building_ids: set[str]) -> str | None:
    place_id = str(place.get("place_id") or "").casefold()
    source_url = str(place.get("source_url") or "").casefold()

    if place_id in _NON_LINKABLE_PLACE_IDS:
        return None

    parts = [
        str(place.get("name") or ""),
        str(place.get("description") or ""),
        str(place.get("source_url") or ""),
        str(place.get("access_notes") or ""),
    ]
    text = " ".join(parts)
    lowered = text.casefold()

    cubo_match = _CUBO_RE.search(lowered)
    if cubo_match:
        number = cubo_match.group(1).lower()
        suffix = (cubo_match.group(2) or "").lower()
        cubo_id = f"cubo-{number}{suffix}"
        if cubo_id in known_building_ids:
            return cubo_id

    cubi_match = _CUBI_RE.search(lowered)
    if cubi_match:
        cubi_prefix = f"cubi-{cubi_match.group(1).lower()}-{cubi_match.group(2).lower()}"
        matches = sorted(
            building_id for building_id in known_building_ids if building_id.startswith(cubi_prefix)
        )
        if len(matches) == 1:
            return matches[0]

    if any(token in lowered for token in ["centro-sanitario", "assistenza sanitaria"]):
        if "centro-sanitario" in known_building_ids:
            return "centro-sanitario"

    if place_id in {"service-diritto-allo-studio", "service-info-isee"} or any(
        token in source_url for token in ["/didattica/diritto-allo-studio/altri-benefici/", "/didattica/diritto-allo-studio/info-isee/"]
    ):
        target = "uffici-centro-residenziale-e-area-didattica"
        if target in known_building_ids:
            return target

    if any(
        token in lowered
        for token in ["front-office-on-line-cr", "serv-cr", "segnalazioni-e-richieste-cr", "centro residenziale"]
    ):
        target = "uffici-centro-residenziale-e-area-didattica"
        if target in known_building_ids:
            return target

    if any(token in lowered for token in ["centro-linguistico", "centro linguistico", " cla "]):
        target = "cla-centro-linguistico-d-ateneo"
        if target in known_building_ids:
            return target

    if any(
        token in lowered
        for token in [
            "/sistema-museale/musnob/paleontologia/",
            "/sistema-museale/musnob/zoologia/",
            "/sistema-museale/musnob/mineralogia-e-petrografia/",
        ]
    ):
        target = "cubo-14b"
        if target in known_building_ids:
            return target

    if any(token in lowered for token in ["centro-sportivo", "centro sportivo", "universitario sportivo", " cus "]):
        target = "centro-universitario-sportivo"
        if target in known_building_ids:
            return target

    if any(token in lowered for token in ["career-service", "cubo 7/11"]):
        matches = sorted(building_id for building_id in known_building_ids if building_id.startswith("cubi-7-11"))
        if len(matches) == 1:
            return matches[0]

    if "teatri-e-cinema" in lowered or "edificio tau" in lowered:
        target = "auditorium-teatro-grande"
        if target in known_building_ids:
            return target

    if "centro-congressi" in lowered or "aula magna" in lowered:
        target = "aula-magna"
        if target in known_building_ids:
            return target

    if "servizi-ict" in lowered:
        target = "cubo-22b"
        if target in known_building_ids:
            return target

    if any(token in lowered for token in ["borse-di-studio", "servizio-foresteria"]):
        target = "uffici-centro-residenziale-e-area-didattica"
        if target in known_building_ids:
            return target

    if "servizio-mensa" in lowered:
        target = "uffici-centro-residenziale-e-area-didattica"
        if target in known_building_ids:
            return target

    if "biblioteche" in lowered:
        target = "cubo-libro"
        if target in known_building_ids:
            return target

    if "polo-infanzia" in lowered or "polo d'infanzia" in lowered:
        target = "auditorium-teatro-grande"
        if target in known_building_ids:
            return target

    return None
