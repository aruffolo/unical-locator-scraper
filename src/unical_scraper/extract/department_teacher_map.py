"""Department-site fallback mapping for teacher -> department resolution."""

from __future__ import annotations

from collections.abc import Callable
import json
import re
from urllib.parse import urljoin, urlparse, urlsplit

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import collapse_whitespace, none_if_empty, person_name_key


_STAFF_LINK_TOKENS = (
    "docent",
    "ricerc",
    "person",
    "people",
    "staff",
    "professor",
    "fascia",
    "assegn",
    "dottor",
)
_PEOPLE_PATH_TOKEN = "/dipartimento/presentazione/persone"
_TEACHER_PATH_RE = re.compile(r"/storage/teachers/([^/?#]+)/?", flags=re.IGNORECASE)
_ADDRESSBOOK_STRUCTURE_RE = re.compile(
    r"https://storage\.portale\.unical\.it/api/ricerca/addressbook/\?[^\"'\s>]*structuretree=([0-9]+)",
    flags=re.IGNORECASE,
)
_ADDRESSBOOK_STRUCTURE_GENERIC_RE = re.compile(
    r"structuretree(?:=|['\"\s:]+)['\"]?([0-9]{6})",
    flags=re.IGNORECASE,
)
DEPARTMENT_FALLBACK_PROGRESS_INTERVAL = 3
ProgressReporter = Callable[[str], None]


def crawl_department_teacher_map(
    departments: list[dict[str, object]],
    client: HttpClient,
    cache: HtmlCache | None = None,
    max_pages_per_department: int = 10,
    progress_reporter: ProgressReporter | None = None,
) -> dict[str, str]:
    """Map teacher keys to department_id by crawling department public websites.

    Mapping keys:
    - `slug:<teacher_profile_slug>`
    - `email_local:<local_part>`
    """
    candidate_mapping: dict[str, set[str]] = {}
    total_departments = len(departments)
    for index, department in enumerate(departments, start=1):
        department_id = department.get("department_id")
        if not isinstance(department_id, str) or not department_id:
            _report_count_progress(
                progress_reporter,
                label="department fallback: scanned",
                current=index,
                total=total_departments,
                interval=DEPARTMENT_FALLBACK_PROGRESS_INTERVAL,
            )
            continue

        base_urls = _department_seed_urls(department)
        for base_url in base_urls:
            for key in _crawl_department_keys(
                base_url=base_url,
                client=client,
                cache=cache,
                max_pages=max_pages_per_department,
            ):
                candidate_mapping.setdefault(key, set()).add(department_id)
        _report_count_progress(
            progress_reporter,
            label="department fallback: scanned",
            current=index,
            total=total_departments,
            interval=DEPARTMENT_FALLBACK_PROGRESS_INTERVAL,
        )

    mapping: dict[str, str] = {}
    for key, department_ids in candidate_mapping.items():
        if len(department_ids) == 1:
            mapping[key] = next(iter(department_ids))
    return mapping


def _report_count_progress(
    progress_reporter: ProgressReporter | None,
    *,
    label: str,
    current: int,
    total: int,
    interval: int,
) -> None:
    if progress_reporter is None or total <= 0:
        return
    if current == total or current % max(interval, 1) == 0:
        progress_reporter(f"{label} {current}/{total}")


def _crawl_department_keys(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None,
    max_pages: int,
) -> set[str]:
    to_visit: list[str] = [base_url]
    visited: set[str] = set()
    keys: set[str] = set()
    base_host = urlparse(base_url).netloc

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html = _try_fetch_html(url=url, client=client, cache=cache)
        if html is None:
            continue

        structure_codes = _extract_addressbook_structure_codes(html)
        for structure_code in structure_codes:
            keys.add(f"department_code:{structure_code}")
            keys.update(
                _crawl_addressbook_keys(
                    structure_code=structure_code,
                    client=client,
                    cache=cache,
                )
            )
        if structure_codes:
            # Addressbook API already returns the complete people list for the structure.
            # Avoid broad HTML navigation when this source is available.
            continue

        page_keys, candidate_links = _extract_keys_and_candidate_links(
            html=html,
            page_url=url,
            allowed_host=base_host,
        )
        keys.update(page_keys)

        for candidate in sorted(candidate_links):
            if candidate not in visited and candidate not in to_visit:
                to_visit.append(candidate)

    return keys


def _department_seed_urls(department: dict[str, object]) -> list[str]:
    seeds: set[str] = set()
    for field in ("website_url", "source_url"):
        value = department.get(field)
        if not isinstance(value, str):
            continue
        normalized = _normalize_seed_url(value)
        if normalized:
            seeds.add(normalized)
            seeds.update(_people_seed_urls(normalized))
    return sorted(seeds)


def _normalize_seed_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc.endswith(".unical.it"):
        return None
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path if parsed.path else "/"
    if not path.endswith("/"):
        path = f"{path}/"
    return f"{base}{path}"


def _people_seed_urls(base_url: str) -> set[str]:
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        f"{origin}{_PEOPLE_PATH_TOKEN}/",
        f"{origin}{_PEOPLE_PATH_TOKEN}/?lang=it",
    }


def _extract_keys_and_candidate_links(
    html: str,
    page_url: str,
    allowed_host: str,
) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html, "html.parser")
    keys: set[str] = set()
    candidate_links: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        if href.startswith("mailto:"):
            local_part = _email_local_part(href.replace("mailto:", "", 1))
            if local_part:
                keys.add(f"email_local:{local_part}")
            continue

        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        link_text = anchor.get_text(" ", strip=True)
        lower_text = link_text.casefold()
        lower_url = absolute.casefold()
        name_key = person_name_key(link_text)
        if name_key:
            keys.add(f"name_key:{name_key}")

        slug = _teacher_slug_from_url(absolute)
        if slug:
            keys.add(f"slug:{slug}")

        if parsed.netloc != allowed_host:
            continue
        if any(token in lower_text for token in _STAFF_LINK_TOKENS) or any(
            token in lower_url for token in _STAFF_LINK_TOKENS
        ):
            candidate_links.add(_strip_query_fragment(absolute))
            continue
        if _is_people_navigation_link(page_url=page_url, candidate_url=absolute, link_text=lower_text):
            candidate_links.add(_strip_query_fragment(absolute))

    return keys, candidate_links


def _teacher_slug_from_url(url: str) -> str | None:
    match = _TEACHER_PATH_RE.search(url)
    if not match:
        return None
    slug = none_if_empty(match.group(1).strip().casefold())
    return slug


def _email_local_part(email: str) -> str | None:
    if "@" not in email:
        return None
    local = none_if_empty(email.split("@", maxsplit=1)[0].strip().casefold())
    return local


def _strip_query_fragment(url: str) -> str:
    parts = urlsplit(url)
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme}://{parts.netloc}{parts.path}{query}"


def _is_people_navigation_link(page_url: str, candidate_url: str, link_text: str) -> bool:
    current = urlparse(page_url)
    candidate = urlparse(candidate_url)
    current_path = current.path.casefold()
    candidate_path = candidate.path.casefold()

    if _PEOPLE_PATH_TOKEN not in current_path and _PEOPLE_PATH_TOKEN not in candidate_path:
        return False
    if _PEOPLE_PATH_TOKEN in candidate_path:
        return True
    if "page=" in candidate.query.casefold():
        return True
    if "next" in link_text or "precedent" in link_text:
        return True
    return False


def _extract_addressbook_structure_codes(html: str) -> set[str]:
    codes = {match.group(1) for match in _ADDRESSBOOK_STRUCTURE_RE.finditer(html)}
    codes.update(match.group(1) for match in _ADDRESSBOOK_STRUCTURE_GENERIC_RE.finditer(html))
    return codes


def _crawl_addressbook_keys(
    structure_code: str,
    client: HttpClient,
    cache: HtmlCache | None,
) -> set[str]:
    keys: set[str] = set()
    next_url = (
        f"https://storage.portale.unical.it/api/ricerca/addressbook/?structuretree={structure_code}"
    )
    visited: set[str] = set()

    while next_url and next_url not in visited:
        visited.add(next_url)
        payload_text = _try_fetch_html(url=next_url, client=client, cache=cache)
        if payload_text is None:
            break
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            break

        results = payload.get("results") if isinstance(payload, dict) else None
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                slug = none_if_empty(str(item.get("ID") or "").strip().casefold())
                if slug:
                    keys.add(f"slug:{slug}")

                normalized_name = _normalized_person_name(item.get("Name"))
                if normalized_name:
                    keys.add(f"name:{normalized_name}")
                name_key = person_name_key(item.get("Name"))
                if name_key:
                    keys.add(f"name_key:{name_key}")

                emails = item.get("Email")
                if isinstance(emails, list):
                    for value in emails:
                        if isinstance(value, str):
                            local_part = _email_local_part(value)
                            if local_part:
                                keys.add(f"email_local:{local_part}")

        raw_next = payload.get("next") if isinstance(payload, dict) else None
        if isinstance(raw_next, str) and raw_next:
            if raw_next.startswith("//"):
                next_url = f"https:{raw_next}"
            else:
                next_url = urljoin(next_url, raw_next)
        else:
            next_url = None

    return keys


def _normalized_person_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return none_if_empty(collapse_whitespace(value).casefold())


def _try_fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str | None:
    try:
        if cache is None:
            return client.get_text(url)
        return cache.get_or_fetch(url, client.get_text)
    except Exception:
        return None
