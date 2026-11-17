import httpx

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return a shared persistent httpx.AsyncClient for fast REST calls."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=12.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _http_client
