"""Filesystem cache for raw HTML snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable


class HtmlCache:
    """Simple deterministic URL->HTML cache."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_url(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.html"

    def get_or_fetch(self, url: str, fetcher: Callable[[str], str]) -> str:
        """Return cached HTML, or fetch and persist it."""
        cache_path = self._path_for_url(url)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        html = fetcher(url)
        cache_path.write_text(html, encoding="utf-8")
        return html
