"""Helpers for exporting Launchpad data safely."""


def csv_safe_value(value):
    """Keep spreadsheet applications from evaluating untrusted text as a formula."""
    if not isinstance(value, str):
        return value
    first = value.lstrip(" \t\r\n\ufeff")[:1]
    if first in {"=", "+", "-", "@"}:
        return "'" + value
    return value
