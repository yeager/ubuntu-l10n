"""Pure package filtering and sorting helpers."""


def filter_and_sort_packages(packages, query: str = "", sort_key: str = "name_asc"):
    """Return a filtered, sorted copy without changing the source package order."""
    normalized_query = query.casefold().strip()
    filtered = [
        package for package in packages
        if normalized_query in package.name.casefold()
    ]

    sort_options = {
        "name_asc": (lambda package: package.name.casefold(), False),
        "most_translated": (lambda package: package.translated_pct, True),
        "least_translated": (lambda package: package.translated_pct, False),
        "most_strings": (lambda package: package.total, True),
        "last_updated": (lambda package: package.last_edited or "", True),
    }
    option = sort_options.get(sort_key)
    if option is None:
        return filtered
    key, reverse = option
    return sorted(filtered, key=key, reverse=reverse)
