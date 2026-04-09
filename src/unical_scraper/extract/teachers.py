"""Teacher extraction helpers."""

from __future__ import annotations

from collections.abc import Callable
import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..utils.html_cache import HtmlCache
from ..utils.http import HttpClient
from ..utils.text import collapse_whitespace, none_if_empty


TEACHERS_API_PATTERN = re.compile(
    r"(?:https?:)?//[^\"'\s>]*?/api/ricerca/teachers/?(?:\?[^\"'\s>]*)?"
    r"|/api/ricerca/teachers/?(?:\?[^\"'\s>]*)?",
    flags=re.IGNORECASE,
)
_ITEM_PAYLOAD_MARKER_RE = re.compile(r"[\"']?item[\"']?\s*:", flags=re.IGNORECASE)
TEACHER_API_PAGE_PROGRESS_INTERVAL = 5
TEACHER_DETAIL_PROGRESS_INTERVAL = 100
ProgressReporter = Callable[[str], None]


@dataclass(frozen=True)
class RawTeacher:
    """Raw teacher record extracted from HTML before normalization."""

    full_name: str
    source_url: str
    email: str | None = None
    phone: str | None = None
    department_name: str | None = None
    department_code: str | None = None
    website_url: str | None = None
    office_hours: str | None = None
    office_reference: str | None = None
    notes: str | None = None


def crawl_teachers(
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None = None,
    detail_enrichment: bool = True,
    progress_reporter: ProgressReporter | None = None,
) -> list[RawTeacher]:
    """Crawl teachers from a UNICAL public page.

    Deterministic behavior:
    - links are deduplicated and sorted
    - output is sorted by normalized name
    """
    _report_progress(progress_reporter, "crawl: start")
    index_html = _fetch_html(base_url, client, cache)

    api_url = _extract_teachers_api_url(index_html=index_html, base_url=base_url)
    if api_url:
        _report_progress(progress_reporter, f"api: discovered endpoint {api_url}")
        teachers_from_api = _crawl_teachers_from_api(
            api_url=api_url,
            base_url=base_url,
            client=client,
            cache=cache,
            detail_enrichment=detail_enrichment,
            progress_reporter=progress_reporter,
        )
        if teachers_from_api:
            _report_progress(
                progress_reporter,
                f"crawl: completed from api with {len(teachers_from_api)} teachers",
            )
            return teachers_from_api

    detail_urls = sorted(_parse_teacher_links(index_html, base_url))
    _report_progress(progress_reporter, f"html fallback: discovered {len(detail_urls)} profile urls")

    teachers: list[RawTeacher] = []
    if not detail_urls:
        # Fallback: page could already be a single profile.
        maybe_teacher = _parse_teacher_detail(index_html, base_url)
        if maybe_teacher:
            teachers.append(maybe_teacher)
        _report_progress(progress_reporter, f"html fallback: extracted {len(teachers)} teachers")
        return teachers

    total_urls = len(detail_urls)
    for index, url in enumerate(detail_urls, start=1):
        html = _fetch_html(url, client, cache)
        teacher = _parse_teacher_detail(html, url)
        if teacher:
            teachers.append(teacher)
        _report_count_progress(
            progress_reporter,
            label="html fallback: processed profiles",
            current=index,
            total=total_urls,
            interval=TEACHER_API_PAGE_PROGRESS_INTERVAL,
        )

    unique_by_key: dict[tuple[str, str | None], RawTeacher] = {}
    for teacher in teachers:
        key = (teacher.full_name.casefold(), teacher.email)
        unique_by_key.setdefault(key, teacher)

    deduped_teachers = sorted(unique_by_key.values(), key=lambda t: t.full_name.casefold())
    _report_progress(progress_reporter, f"html fallback: deduped to {len(deduped_teachers)} teachers")
    return deduped_teachers


def _fetch_html(url: str, client: HttpClient, cache: HtmlCache | None) -> str:
    if cache is None:
        return client.get_text(url)
    return cache.get_or_fetch(url, client.get_text)


def _parse_teacher_links(index_html: str, base_url: str) -> set[str]:
    """Extract teacher profile links from a teachers listing page."""
    soup = BeautifulSoup(index_html, "html.parser")
    base_host = urlparse(base_url).netloc

    links: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if href.startswith("mailto:"):
            continue

        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc and parsed.netloc != base_host:
            continue
        if "/storage/teachers/" in parsed.path:
            links.add(_strip_query_and_fragment(absolute))
            continue

        lower_url = absolute.lower()
        lower_text = anchor.get_text(" ", strip=True).lower()
        if any(token in lower_url for token in ["/privacy", "/cookie", "/credits", "/sitemap"]):
            continue
        if any(token in lower_url for token in ["docent", "teacher", "profile", "person"]):
            links.add(absolute)
        elif "docente" in lower_text or "prof." in lower_text:
            links.add(absolute)

    return links


def _parse_teacher_detail(detail_html: str, source_url: str) -> RawTeacher | None:
    """Parse one teacher profile page into a `RawTeacher` record."""
    payload = _extract_teacher_results_payload(detail_html)
    soup = BeautifulSoup(detail_html, "html.parser")

    email = None
    email_link = soup.select_one("a[href^='mailto:']")
    if email_link:
        email = none_if_empty(email_link.get("href", "").replace("mailto:", "").strip())

    website_url = None
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if href.startswith("http") and "mailto:" not in href:
            website_url = href
            break

    if payload:
        full_name = _teacher_full_name_from_payload(payload) or _extract_heading_name(soup)
        if not full_name:
            return None

        payload_email = _extract_first_string(payload.get("TeacherEmail"))
        payload_website = _extract_first_string(payload.get("TeacherWebSite"))
        payload_phone = _extract_first_string(payload.get("TeacherTelOffice"))
        office = _extract_text(payload.get("TeacherOffice"))
        office_reference = ", ".join(_extract_string_list(payload.get("TeacherOfficeReference")))
        notes_parts = []
        if office:
            notes_parts.append(f"Office: {office}")
        if office_reference:
            notes_parts.append(f"Office references: {office_reference}")
        notes = " | ".join(notes_parts) if notes_parts else None

        return RawTeacher(
            full_name=full_name,
            source_url=source_url,
            email=payload_email or email,
            phone=payload_phone,
            department_name=_extract_text(payload.get("TeacherDepartmentName")),
            department_code=_extract_text(payload.get("TeacherDepartmentCod")),
            website_url=payload_website or website_url,
            office_hours=_extract_text(payload.get("ReceptionHours")),
            office_reference=office_reference or None,
            notes=notes,
        )

    name_candidate = _extract_heading_name(soup)
    if not name_candidate:
        return None

    return RawTeacher(
        full_name=name_candidate,
        source_url=source_url,
        email=email,
        website_url=website_url,
    )


def _extract_teachers_api_url(index_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(index_html, "html.parser")
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if "/api/ricerca/teachers" not in href:
            continue
        candidate = _to_absolute_url(base_url=base_url, href=href)
        return _normalize_teachers_api_url(candidate)

    for match in TEACHERS_API_PATTERN.finditer(index_html):
        candidate = _clean_url_candidate(match.group(0))
        if not candidate:
            continue
        absolute = _to_absolute_url(base_url=base_url, href=candidate)
        return _normalize_teachers_api_url(absolute)
    return None


def _to_absolute_url(base_url: str, href: str) -> str:
    if href.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{href}"
    return urljoin(base_url, href)


def _crawl_teachers_from_api(
    api_url: str,
    base_url: str,
    client: HttpClient,
    cache: HtmlCache | None,
    detail_enrichment: bool,
    progress_reporter: ProgressReporter | None,
) -> list[RawTeacher]:
    teachers: list[RawTeacher] = []
    api_url = _normalize_teachers_api_url(api_url)
    next_url: str | None = _with_page_size(api_url, page_size=200)
    visited: set[str] = set()
    page_count = 0
    detail_attempts = 0

    while next_url and next_url not in visited:
        visited.add(next_url)
        page_count += 1
        payload = json.loads(_fetch_html(next_url, client, cache))
        results = payload.get("results", []) if isinstance(payload, dict) else []
        if not isinstance(results, list):
            results = []
        _report_progress(
            progress_reporter,
            f"api pages: loaded page {page_count} with {len(results)} teachers",
        )

        for item in results:
            if not isinstance(item, dict):
                continue

            full_name = _extract_text(item.get("TeacherName"))
            if not full_name:
                continue

            email = _extract_first_email(item.get("Email"))
            teacher_id = _extract_text(item.get("TeacherID"))
            department_name = _extract_first_string(item.get("TeacherDepartmentName"))
            department_code = _extract_first_string(item.get("TeacherDepartmentCod"))
            website_url = _teacher_profile_url(
                base_url=base_url,
                email=email,
                teacher_id=teacher_id,
            )
            source_url = website_url or api_url
            detail = None
            if detail_enrichment:
                detail_attempts += 1
                detail = _fetch_teacher_detail_payload(
                    api_url=api_url,
                    teacher_id=teacher_id,
                    client=client,
                    cache=cache,
                )
                _report_interval_progress(
                    progress_reporter,
                    label="api details: fetched",
                    current=detail_attempts,
                    interval=TEACHER_DETAIL_PROGRESS_INTERVAL,
                )
            detail_department_name = (
                _extract_first_string(detail.get("TeacherDepartmentName")) if detail else None
            )
            detail_department_code = (
                _extract_first_string(detail.get("TeacherDepartmentCod")) if detail else None
            )
            office_reference = _extract_first_string(
                detail.get("TeacherOfficeReference") if detail else None
            )
            office = _extract_text(detail.get("TeacherOffice")) if detail else None
            notes = office
            if office and office_reference:
                notes = f"Office: {office} | Office references: {office_reference}"
            elif office_reference:
                notes = f"Office references: {office_reference}"

            teachers.append(
                RawTeacher(
                    full_name=full_name,
                    source_url=source_url,
                    email=(_extract_first_email(detail.get("TeacherEmail")) if detail else None) or email,
                    phone=_extract_first_string(detail.get("TeacherTelOffice")) if detail else None,
                    department_name=detail_department_name or department_name,
                    department_code=detail_department_code or department_code,
                    website_url=(_extract_first_string(detail.get("TeacherWebSite")) if detail else None)
                    or website_url,
                    office_hours=_extract_text(detail.get("ReceptionHours")) if detail else None,
                    office_reference=office_reference,
                    notes=notes,
                )
            )

        raw_next = payload.get("next") if isinstance(payload, dict) else None
        if isinstance(raw_next, str) and raw_next:
            next_url = _with_page_size(
                _to_absolute_url(base_url=api_url, href=raw_next),
                page_size=200,
            )
        else:
            next_url = None

    if not detail_enrichment:
        _report_progress(progress_reporter, "api details: disabled")
    elif detail_attempts > 0:
        _report_progress(progress_reporter, f"api details: fetched {detail_attempts}")

    unique_by_key: dict[tuple[str, str | None], RawTeacher] = {}
    for teacher in teachers:
        key = (teacher.full_name.casefold(), teacher.email)
        unique_by_key.setdefault(key, teacher)

    deduped_teachers = sorted(unique_by_key.values(), key=lambda teacher: teacher.full_name.casefold())
    _report_progress(
        progress_reporter,
        f"api: deduped to {len(deduped_teachers)} teachers across {page_count} pages",
    )
    return deduped_teachers


def _extract_first_email(value: object) -> str | None:
    email = _extract_first_string(value)
    if not email:
        return None
    return none_if_empty(email.strip())


def _report_progress(progress_reporter: ProgressReporter | None, message: str) -> None:
    if progress_reporter is None:
        return
    progress_reporter(message)


def _report_count_progress(
    progress_reporter: ProgressReporter | None,
    *,
    label: str,
    current: int,
    total: int,
    interval: int,
) -> None:
    if progress_reporter is None:
        return
    effective_total = max(total, current)
    if current == effective_total or current % max(interval, 1) == 0:
        progress_reporter(f"{label} {current}/{effective_total}")


def _report_interval_progress(
    progress_reporter: ProgressReporter | None,
    *,
    label: str,
    current: int,
    interval: int,
) -> None:
    if progress_reporter is None:
        return
    if current % max(interval, 1) == 0:
        progress_reporter(f"{label} {current}")


def _teacher_profile_url(base_url: str, email: str | None, teacher_id: str | None) -> str | None:
    slug = None
    if email and "@" in email:
        local_part = email.split("@", maxsplit=1)[0].strip()
        slug = none_if_empty(local_part)
    if not slug:
        slug = teacher_id
    if not slug:
        return None
    quoted_slug = quote(slug, safe="._-")
    return _to_absolute_url(base_url=base_url, href=f"/storage/teachers/{quoted_slug}/")


def _fetch_teacher_detail_payload(
    api_url: str,
    teacher_id: str | None,
    client: HttpClient,
    cache: HtmlCache | None,
) -> dict[str, object] | None:
    if not teacher_id:
        return None

    detail_url = _teacher_detail_api_url(api_url=api_url, teacher_id=teacher_id)
    try:
        payload = json.loads(_fetch_html(detail_url, client, cache))
    except Exception:
        return None

    results = payload.get("results") if isinstance(payload, dict) else None
    return results if isinstance(results, dict) else None


def _teacher_detail_api_url(api_url: str, teacher_id: str) -> str:
    parts = urlsplit(api_url)
    base_path = parts.path.rstrip("/")
    quoted_teacher_id = quote(teacher_id, safe="")
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            f"{base_path}/{quoted_teacher_id}/",
            "format=json",
            "",
        )
    )


def _extract_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return none_if_empty(collapse_whitespace(value))


def _extract_first_string(value: object) -> str | None:
    if isinstance(value, list):
        for entry in value:
            if not isinstance(entry, str):
                continue
            text = _extract_text(entry)
            if text:
                return text
        return None
    return _extract_text(value)


def _extract_string_list(value: object) -> list[str]:
    if isinstance(value, str):
        text = _extract_text(value)
        return [text] if text else []
    if not isinstance(value, list):
        return []

    results: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            continue
        text = _extract_text(entry)
        if text:
            results.append(text)
    return results


def _extract_heading_name(soup: BeautifulSoup) -> str | None:
    for selector in ["h1", "h2", ".page-title", ".title"]:
        element = soup.select_one(selector)
        if element:
            text = none_if_empty(collapse_whitespace(element.get_text(" ", strip=True)))
            if text:
                return text

    title = soup.title.string.strip() if soup.title and soup.title.string else None
    if not title:
        return None
    return none_if_empty(collapse_whitespace(title))


def _extract_teacher_results_payload(detail_html: str) -> dict[str, object] | None:
    for match in _ITEM_PAYLOAD_MARKER_RE.finditer(detail_html):
        index = match.start()
        object_start = detail_html.find("{", match.end())
        if object_start == -1:
            continue

        object_text, _ = _extract_balanced_json_object(detail_html, object_start)
        if object_text:
            try:
                parsed = json.loads(object_text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                results = parsed.get("results")
                if isinstance(results, dict):
                    return results
            if isinstance(parsed, dict):
                return parsed

    return None


def _extract_balanced_json_object(text: str, start_index: int) -> tuple[str | None, int]:
    if start_index < 0 or start_index >= len(text) or text[start_index] != "{":
        return None, start_index + 1

    depth = 0
    in_string = False
    escaped = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1], index + 1

    return None, len(text)


def _teacher_full_name_from_payload(payload: dict[str, object]) -> str | None:
    first_name = _extract_text(payload.get("TeacherFirstName"))
    last_name = _extract_text(payload.get("TeacherLastName"))
    if first_name and last_name:
        return f"{first_name} {last_name}"
    return _extract_text(payload.get("TeacherName"))


def _normalize_teachers_api_url(url: str) -> str:
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["format"] = "json"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))


def _clean_url_candidate(candidate: str) -> str:
    cleaned = candidate.strip().strip("\"'`")
    return cleaned.rstrip("),;")


def _strip_query_and_fragment(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _with_page_size(url: str, page_size: int) -> str:
    parts = urlsplit(url)
    params = dict(parse_qsl(parts.query, keep_blank_values=True))
    params["page_size"] = str(page_size)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
