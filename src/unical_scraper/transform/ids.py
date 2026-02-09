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
