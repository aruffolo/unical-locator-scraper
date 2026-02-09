"""Deterministic ID helpers for canonical entities."""

from __future__ import annotations

from ..utils.text import slugify


def stable_slug(value: str) -> str:
    """Return a stable slug and fail on empty values."""
    slug = slugify(value)
    if not slug:
        raise ValueError("Cannot generate slug from an empty value")
    return slug


def make_person_id(full_name: str, email: str | None = None) -> str:
    """Create stable person IDs.

    Rule for MVP:
    - normalize full name
    - use `surname-name` order for two+ tokens
    - fallback to email local-part when name is missing
    """
    name_slug = slugify(full_name)
    if name_slug:
        tokens = [token for token in name_slug.split("-") if token]
        if len(tokens) >= 2:
            surname = tokens[-1]
            given = "-".join(tokens[:-1])
            return f"{surname}-{given}"
        return name_slug

    if email:
        local_part = email.split("@", maxsplit=1)[0]
        fallback = slugify(local_part)
        if fallback:
            return fallback

    raise ValueError("Cannot generate person_id without full_name or email")


def make_department_id(name: str) -> str:
    """Create stable department IDs from canonical name."""
    return stable_slug(name)


def make_building_id(name: str) -> str:
    """Create stable building IDs from canonical name."""
    return stable_slug(name)


def make_place_id(name: str, place_type: str) -> str:
    """Create stable place IDs from type + canonical name."""
    return stable_slug(f"{place_type.lower()}-{name}")


def make_aula_id(name: str, building_id: str | None = None, short_code: str | None = None) -> str:
    """Create stable aula IDs from best available deterministic tokens."""
    primary = short_code if short_code else name
    primary_slug = stable_slug(primary)
    if primary_slug.startswith("aula-"):
        primary_slug = primary_slug[len("aula-") :]

    if building_id:
        if primary_slug == building_id or building_id.endswith(f"-{primary_slug}"):
            return stable_slug(f"aula-{primary_slug}")
        return stable_slug(f"aula-{primary_slug}-{building_id}")
    return stable_slug(f"aula-{primary_slug}")
