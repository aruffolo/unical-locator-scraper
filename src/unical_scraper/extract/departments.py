"""Departments extraction skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawDepartment:
    """Raw department record from source pages."""

    name: str
    source_url: str
    email: str | None = None
    phone: str | None = None
    website_url: str | None = None


def crawl_departments(base_url: str) -> list[RawDepartment]:
    """Return departments extracted from UNICAL pages.

    TODO: implement source-specific parsing for departments pages.
    """
    _ = base_url
    return []
