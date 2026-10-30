"""Scrape translation statistics from Launchpad with caching and rate limiting."""

import json
import logging
import math
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

CACHE_DIR = Path.home() / ".cache" / "ubuntu-l10n"
CACHE_FILE = CACHE_DIR / "cache.json"
CONFIG_DIR = Path.home() / ".config" / "ubuntu-l10n"
CONFIG_FILE = CONFIG_DIR / "config.json"

REQUEST_DELAY = 0.8  # seconds between requests
_CACHE_WRITE_LOCK = threading.Lock()
_LOGGER = logging.getLogger(__name__)


@dataclass
class PackageStats:
    """Translation statistics for a single package/template."""
    name: str
    translated_pct: float
    untranslated: int
    need_review: int
    changed: int
    total: int
    last_edited: str
    last_editor: str
    translate_url: str

    @property
    def translated(self) -> int:
        return self.total - self.untranslated

    @property
    def fuzzy(self) -> int:
        return self.need_review


DISTRO_VERSIONS = {
    "stonking": "26.10",
    "resolute": "26.04",
    "questing": "25.10",
    "plucky": "25.04",
    "oracular": "24.10",
    "noble": "24.04 LTS",
    "jammy": "22.04 LTS",
    "focal": "20.04 LTS",
}
EOL_DISTROS = frozenset({"questing", "plucky", "oracular"})
ESM_DISTROS = frozenset({"focal"})

# Language codes for common Ubuntu languages
LANGUAGES = {
    "sv": "Swedish",
    "da": "Danish",
    "nb": "Norwegian Bokmål",
    "nn": "Norwegian Nynorsk",
    "fi": "Finnish",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt_BR": "Portuguese (Brazil)",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "zh_CN": "Chinese (Simplified)",
    "zh_TW": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "cs": "Czech",
    "hu": "Hungarian",
    "ro": "Romanian",
    "tr": "Turkish",
    "el": "Greek",
    "he": "Hebrew",
    "id": "Indonesian",
    "ca": "Catalan",
    "gl": "Galician",
    "eu": "Basque",
    "pt": "Portuguese",
}

BASE_URL = "https://translations.launchpad.net/ubuntu"


class LaunchpadResponseError(ValueError):
    """Raised when Launchpad returns a page without usable statistics."""


def _launchpad_translation_url(href: object) -> str | None:
    """Accept only HTTPS links under the Ubuntu translations service."""
    if not isinstance(href, str) or not href:
        return None
    parsed_href = urlparse(href)
    if parsed_href.scheme and parsed_href.scheme != "https":
        return None
    if parsed_href.netloc and parsed_href.netloc != "translations.launchpad.net":
        return None
    url = urljoin("https://translations.launchpad.net", href)
    parsed_url = urlparse(url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.netloc != "translations.launchpad.net"
        or not parsed_url.path.startswith("/ubuntu/")
    ):
        return None
    return url


def load_config() -> dict:
    """Load config from ~/.config/ubuntu-l10n/config.json."""
    try:
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return config if isinstance(config, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _atomic_write_json(path: Path, data: dict):
    """Write JSON atomically with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def save_config(config: dict, path: Path | None = None):
    """Save config atomically to the main config file or an explicit JSON path."""
    _atomic_write_json(CONFIG_FILE if path is None else Path(path), config)


def _cache_key(distro: str, lang: str) -> str:
    return f"{distro}_{lang}"


def load_cache(distro: str, lang: str) -> tuple[list | None, float | None]:
    """Load cached data. Returns (data, timestamp) or (None, None)."""
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        key = _cache_key(distro, lang)
        if key in cache:
            entry = cache[key]
            if isinstance(entry, dict) and isinstance(entry.get("data"), list):
                timestamp = entry.get("timestamp")
                if isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool):
                    try:
                        timestamp = float(timestamp)
                    except (OverflowError, ValueError):
                        timestamp = None
                    if timestamp is not None and math.isfinite(timestamp) and timestamp >= 0:
                        return entry["data"], timestamp
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    return None, None


def save_cache(distro: str, lang: str, data: list[dict]) -> bool:
    """Save data to cache with current timestamp, returning whether it worked."""
    with _CACHE_WRITE_LOCK:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            cache = {}
        cache[_cache_key(distro, lang)] = {
            "data": data,
            "timestamp": time.time(),
        }
        try:
            _atomic_write_json(CACHE_FILE, cache)
        except OSError:
            _LOGGER.warning("Could not save Launchpad translation cache")
            return False
        return True


def _request_with_retry(session: requests.Session, url: str,
                        max_retries: int = 4) -> requests.Response:
    """GET with bounded exponential backoff for transient network/server errors."""
    attempts = max(1, max_retries)
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=30)
        except (requests.Timeout, requests.ConnectionError):
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** (attempt + 1))
            continue

        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt + 1 == attempts:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After") if response.status_code == 429 else None
            try:
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        retry_at = parsedate_to_datetime(retry_after)
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=timezone.utc)
                        wait = (retry_at - datetime.now(timezone.utc)).total_seconds()
                    wait = min(max(wait, 0), 60)
                else:
                    wait = 2 ** (attempt + 1)
            except (TypeError, ValueError, OverflowError):
                wait = 2 ** (attempt + 1)
            time.sleep(wait)
            continue

        response.raise_for_status()
        return response

    raise requests.RequestException("Request failed without a response")


def get_lang_url(distro: str, lang: str, batch: int = 300, start: int = 0) -> str:
    url = f"{BASE_URL}/{distro}/+lang/{lang}/+index?batch={batch}"
    if start > 0:
        url += f"&start={start}"
    return url


def parse_page(html: str, distro: str) -> list[PackageStats]:
    """Parse a single Launchpad translation page."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="translation-stats")
    if not table:
        raise LaunchpadResponseError("Launchpad returned a page without translation statistics")

    packages = []
    for row in table.find_all("tr", id=True):
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        # Template name and URL
        name_link = cells[0].find("a")
        if not name_link:
            continue
        name = name_link.get_text(strip=True)
        translate_url = _launchpad_translation_url(name_link.get("href"))
        if not name or not translate_url:
            continue

        # Translated percentage
        sortkeys = cells[1].find_all("span", class_="sortkey")
        if not sortkeys:
            raise LaunchpadResponseError("Launchpad returned a package without a translation percentage")
        try:
            translated_pct = float(sortkeys[0].get_text(strip=True))
        except ValueError as error:
            raise LaunchpadResponseError("Launchpad returned an invalid translation percentage") from error
        if not math.isfinite(translated_pct) or not 0 <= translated_pct <= 100:
            raise LaunchpadResponseError("Launchpad returned an invalid translation percentage")

        # Untranslated, need review, changed
        def get_int(cell):
            sk = cell.find("span", class_="sortkey")
            if sk:
                try:
                    # Launchpad may group large counts with commas or spaces.
                    digits = re.sub(r"\D", "", sk.get_text(strip=True))
                    return int(digits) if digits else 0
                except ValueError:
                    return 0
            return 0

        untranslated = get_int(cells[2])
        need_review = get_int(cells[3])
        changed = get_int(cells[4])

        # Total
        try:
            # Keep totals consistent with the grouped sort-key counts above.
            digits = re.sub(r"\D", "", cells[5].get_text("", strip=True))
            total = int(digits) if digits else 0
        except (ValueError, IndexError):
            total = 0

        # Last edited
        time_tag = cells[6].find("time")
        last_edited = time_tag.get_text(strip=True) if time_tag else ""

        # Last editor
        editor_link = cells[7].find("a")
        last_editor = editor_link.get_text(strip=True) if editor_link else ""

        packages.append(PackageStats(
            name=name,
            translated_pct=translated_pct,
            untranslated=untranslated,
            need_review=need_review,
            changed=changed,
            total=total,
            last_edited=last_edited,
            last_editor=last_editor,
            translate_url=translate_url,
        ))

    return packages


def get_total_count(html: str) -> int:
    """Extract total result count from page."""
    soup = BeautifulSoup(html, "lxml")
    nav = soup.find("td", class_="batch-navigation-index")
    if nav:
        text = nav.get_text(" ", strip=True)
        m = re.search(r"\bof\s+([\d][\d,.\s]*)", text, re.IGNORECASE)
        if m:
            count = re.sub(r"[,.\s]", "", m.group(1))
            return int(count)
    raise LaunchpadResponseError("Launchpad returned a page without a result count")


def _packages_to_dicts(packages: list[PackageStats]) -> list[dict]:
    return [asdict(p) for p in packages]


def _dicts_to_packages(dicts: list[dict]) -> list[PackageStats]:
    if not isinstance(dicts, list):
        raise ValueError("Cached package data must be a list")
    required = set(PackageStats.__dataclass_fields__)
    string_fields = ("name", "last_edited", "last_editor", "translate_url")
    integer_fields = ("untranslated", "need_review", "changed", "total")
    packages = []
    for item in dicts:
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError("Cached package entry has an unexpected structure")
        if any(not isinstance(item[field], str) for field in string_fields):
            raise ValueError("Cached package text fields must be strings")
        percentage = item["translated_pct"]
        if isinstance(percentage, bool) or not isinstance(percentage, (int, float)):
            raise ValueError("Cached translation percentage is invalid")
        try:
            percentage = float(percentage)
        except (OverflowError, ValueError):
            raise ValueError("Cached translation percentage is invalid") from None
        if not math.isfinite(percentage) or not 0 <= percentage <= 100:
            raise ValueError("Cached translation percentage is invalid")
        if any(
            isinstance(item[field], bool)
            or not isinstance(item[field], int)
            or item[field] < 0
            for field in integer_fields
        ):
            raise ValueError("Cached package counts must be non-negative integers")
        if item["untranslated"] > item["total"]:
            raise ValueError("Cached untranslated count exceeds its total")
        packages.append(PackageStats(**item))
    return packages


def fetch_all_packages(distro: str, lang: str, callback=None,
                       cache_cb=None, force: bool = False) -> list[PackageStats]:
    """Fetch all translation packages, paginating as needed.

    callback(loaded, total) — progress updates.
    cache_cb(packages, age_minutes) — called if cached data is available.
    force — skip cache.
    """
    # Check cache first. Keep stale data available while refreshing so the UI
    # can still show useful results if Launchpad is temporarily unavailable.
    if not force:
        cached_data, cached_ts = load_cache(distro, lang)
        if cached_data is not None and cached_ts is not None:
            try:
                packages = _dicts_to_packages(cached_data)
            except (TypeError, ValueError):
                packages = None
            if packages is not None:
                age_seconds = time.time() - cached_ts
                age_minutes = int(age_seconds / 60) if age_seconds >= 0 else None
                cache_is_fresh = age_seconds >= 0 and age_seconds < 3600
                if cache_cb:
                    cache_cb(packages, age_minutes)
                if cache_is_fresh:
                    return packages

    session = requests.Session()
    from . import __version__
    session.headers["User-Agent"] = f"ubuntu-l10n/{__version__}"

    batch = 300
    all_packages = []

    # First page
    url = get_lang_url(distro, lang, batch, 0)
    resp = _request_with_retry(session, url)

    total = get_total_count(resp.text)
    packages = parse_page(resp.text, distro)
    if total > 0 and not packages:
        raise LaunchpadResponseError("Launchpad reported results but returned no translation templates")
    all_packages.extend(packages)

    if callback:
        callback(len(all_packages), total)

    # Remaining pages
    start = batch
    while start < total:
        time.sleep(REQUEST_DELAY)
        url = get_lang_url(distro, lang, batch, start)
        resp = _request_with_retry(session, url)
        packages = parse_page(resp.text, distro)
        if not packages:
            raise LaunchpadResponseError("Launchpad returned an empty page before all results were loaded")
        all_packages.extend(packages)
        start += batch
        if callback:
            callback(len(all_packages), total)

    if len(all_packages) != total:
        raise LaunchpadResponseError(
            f"Launchpad reported {total} translation templates but only "
            f"{len(all_packages)} were loaded",
        )

    # Save to cache
    save_cache(distro, lang, _packages_to_dicts(all_packages))

    return all_packages
