"""Campus services extraction skeleton."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawService:
    """Raw service/office record from source pages."""

    name: str
    source_url: str
    description: str | None = None


def crawl_services(base_url: str) -> list[RawService]:
    """Return service records extracted from UNICAL pages.

    TODO: implement source-specific parsing for services and secretary offices.
    """
    _ = base_url
    return []
