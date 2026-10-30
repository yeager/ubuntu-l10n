"""Resolve saved selectors without trusting stale configuration values."""


def preferred_index(items: list[str], preferred: object, fallback: object = None) -> int:
    """Return the index of a supported saved value or its fallback."""
    if preferred in items:
        return items.index(preferred)
    if fallback in items:
        return items.index(fallback)
    return 0
