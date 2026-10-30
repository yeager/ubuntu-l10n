"""Helpers for selecting the app's default translation language."""

import locale
import os


def _language_code(value: str, supported_languages) -> str | None:
    """Return a supported language code from a locale-style string."""
    value = value.split(":", 1)[0].split(".", 1)[0].split("@", 1)[0]
    if value.casefold() in {"c", "posix", ""}:
        return None

    parts = value.replace("-", "_").split("_", 1)
    language = parts[0].lower()
    territory = parts[1].upper() if len(parts) == 2 else ""
    if territory and f"{language}_{territory}" in supported_languages:
        return f"{language}_{territory}"
    if language in supported_languages:
        return language
    return None


def get_system_language(supported_languages, environ=None, locale_name=None) -> str:
    """Pick a supported translation language from the desktop locale.

    ``LANGUAGE`` is a gettext preference list, so its first supported value
    takes precedence. Otherwise the standard locale environment variables are
    checked in their precedence order. Swedish remains the app's fallback.
    Optional arguments keep the function deterministic in tests.
    """
    supported_codes = set(supported_languages)
    environment = os.environ if environ is None else environ
    language_list = environment.get("LANGUAGE", "")
    for candidate in language_list.split(":"):
        code = _language_code(candidate, supported_codes)
        if code:
            return code

    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        code = _language_code(environment.get(key, ""), supported_codes)
        if code:
            return code

    if locale_name is None:
        try:
            locale_name = locale.getlocale()[0]
        except (ValueError, TypeError):
            locale_name = None
    return _language_code(locale_name or "", supported_codes) or "sv"
