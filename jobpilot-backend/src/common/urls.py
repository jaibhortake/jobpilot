from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = frozenset(
    {"gclid", "fbclid", "_gl", "ref", "source", "src"}
)


class UnsafeUrl(ValueError):
    pass


def safe_http_url(value: str) -> str:
    """Return the stripped URL if it is http(s) with a host, else raise UnsafeUrl."""
    url = value.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrl(url)
    return url


def canonical_url(value: str) -> str:
    """Drop the fragment and tracking params, and sort the remaining params."""
    parts = urlsplit(safe_http_url(value))
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k not in TRACKING_PARAMS and not k.startswith("utm_")
    )
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urlencode(query), ""))
