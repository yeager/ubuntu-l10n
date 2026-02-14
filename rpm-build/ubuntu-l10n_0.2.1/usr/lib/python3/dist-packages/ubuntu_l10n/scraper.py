"""Scrape translation statistics from Launchpad with caching and rate limiting."""

import json
import re
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable

import requests
from bs4 import BeautifulSoup

CACHE_DIR = Path.home() / ".cache" / "ubuntu-l10n"
CACHE_FILE = CACHE_DIR / "cache.json"
CONFIG_DIR = Path.home() / ".config" / "ubuntu-l10n"
CONFIG_FILE = CONFIG_DIR / "config.json"

REQUEST_DELAY = 0.8  # seconds between requests


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
    "resolute": "26.04",
    "questing": "25.10",
    "plucky": "25.04",
    "oracular": "24.10",
    "noble": "24.04 LTS",
    "focal": "20.04 LTS",
}

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


def load_config() -> dict:
    """Load config from ~/.config/ubuntu-l10n/config.json."""
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(config: dict):
    """Save config to ~/.config/ubuntu-l10n/config.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))


def _cache_key(distro: str, lang: str) -> str:
    return f"{distro}_{lang}"


def load_cache(distro: str, lang: str) -> tuple[list | None, float | None]:
    """Load cached data. Returns (data, timestamp) or (None, None)."""
    try:
        cache = json.loads(CACHE_FILE.read_text())
        key = _cache_key(distro, lang)
        if key in cache:
            entry = cache[key]
            return entry["data"], entry["timestamp"]
    except Exception:
        pass
    return None, None


def save_cache(distro: str, lang: str, data: list[dict]):
    """Save data to cache with current timestamp."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        cache = json.loads(CACHE_FILE.read_text())
    except Exception:
        cache = {}
    cache[_cache_key(distro, lang)] = {
        "data": data,
        "timestamp": time.time(),
    }
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def _request_with_retry(session: requests.Session, url: str,
                        max_retries: int = 4) -> requests.Response:
    """Make a GET request with exponential backoff on 429."""
    for attempt in range(max_retries):
        r = session.get(url, timeout=30)
        if r.status_code == 429:
            wait = 2 ** (attempt + 1)  # 2, 4, 8, 16
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    # Final attempt
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r


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
        return []

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
        translate_url = "https://translations.launchpad.net" + name_link["href"]

        # Translated percentage
        sortkeys = cells[1].find_all("span", class_="sortkey")
        translated_pct = float(sortkeys[0].get_text(strip=True)) if sortkeys else 0.0

        # Untranslated, need review, changed
        def get_int(cell):
            sk = cell.find("span", class_="sortkey")
            if sk:
                try:
                    return int(sk.get_text(strip=True))
                except ValueError:
                    return 0
            return 0

        untranslated = get_int(cells[2])
        need_review = get_int(cells[3])
        changed = get_int(cells[4])

        # Total
        try:
            total = int(cells[5].get_text(strip=True))
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
        text = nav.get_text()
        m = re.search(r"of\s+(\d+)", text)
        if m:
            return int(m.group(1))
    return 0


def _packages_to_dicts(packages: list[PackageStats]) -> list[dict]:
    return [asdict(p) for p in packages]


def _dicts_to_packages(dicts: list[dict]) -> list[PackageStats]:
    return [PackageStats(**d) for d in dicts]


def fetch_all_packages(distro: str, lang: str, callback=None,
                       cache_cb=None, force: bool = False) -> list[PackageStats]:
    """Fetch all translation packages, paginating as needed.

    callback(loaded, total) — progress updates.
    cache_cb(packages, age_minutes) — called if cached data is available.
    force — skip cache.
    """
    # Check cache first
    if not force:
        cached_data, cached_ts = load_cache(distro, lang)
        if cached_data and cached_ts:
            age_seconds = time.time() - cached_ts
            if age_seconds < 3600:  # < 1 hour
                age_minutes = int(age_seconds / 60)
                packages = _dicts_to_packages(cached_data)
                if cache_cb:
                    cache_cb(packages, age_minutes)
                return packages

    session = requests.Session()
    session.headers["User-Agent"] = "ubuntu-l10n/0.1.0"

    batch = 300
    all_packages = []

    # First page
    url = get_lang_url(distro, lang, batch, 0)
    resp = _request_with_retry(session, url)

    total = get_total_count(resp.text)
    packages = parse_page(resp.text, distro)
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
        all_packages.extend(packages)
        start += batch
        if callback:
            callback(len(all_packages), total)

    # Save to cache
    save_cache(distro, lang, _packages_to_dicts(all_packages))

    return all_packages
