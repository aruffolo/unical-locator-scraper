"""String normalization helpers."""

from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")
_SLUG_INVALID_RE = re.compile(r"[^a-z0-9]+")


def collapse_whitespace(value: str | None) -> str:
    """Collapse consecutive whitespace to single spaces."""
    if value is None:
        return ""
    return _WHITESPACE_RE.sub(" ", value).strip()


def none_if_empty(value: str | None) -> str | None:
    """Return None for empty/blank strings."""
    collapsed = collapse_whitespace(value)
    return collapsed if collapsed else None


def slugify(value: str | None) -> str:
    """Create URL-safe stable slugs from free-form text."""
    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower().strip()
    slug = _SLUG_INVALID_RE.sub("-", lowered).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug
