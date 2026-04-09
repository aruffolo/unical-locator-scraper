"""Filesystem cache for raw HTML snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable


class HtmlCache:
    """Simple deterministic URL->HTML cache."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, object] | None = None,
    ) -> Path:
        cache_key = {
            "method": method.upper(),
            "payload": payload,
            "url": url,
        }
        digest = hashlib.sha256(
            json.dumps(cache_key, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return self.cache_dir / f"{digest}.cache"

    def get_or_fetch(self, url: str, fetcher: Callable[[str], str]) -> str:
        """Return cached HTML, or fetch and persist it."""
        return self.get_or_fetch_request(
            method="GET",
            url=url,
            payload=None,
            fetcher=lambda: fetcher(url),
        )

    def get_or_fetch_request(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, object] | None,
        fetcher: Callable[[], str],
    ) -> str:
        """Return cached response body for one deterministic request key."""
        cache_path = self._path_for_request(method=method, url=url, payload=payload)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        response_text = fetcher()
        cache_path.write_text(response_text, encoding="utf-8")
        return response_text
