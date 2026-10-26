"""Web search through a self-hosted meta-search engine — degoog by default,
SearXNG as the drop-in fallback. Never a search vendor's own API: the query
goes from this machine to the local instance, which fans it out to the
upstream engines itself.

Both providers speak plain JSON over httpx, so swapping is one .env line
(`search_provider=searxng`). A new provider only has to satisfy
SearchProvider — tests/contracts/test_search_contract.py checks that.
"""

from typing import Protocol

import httpx
from pydantic import BaseModel

from settings import settings

_TIMEOUT_SECONDS = 15.0


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


class SearchError(RuntimeError):
    """Raised with a sentence an agent can act on (or read out), never a
    raw traceback — the caller hands str(exc) straight back to the LLM."""


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]: ...


async def _get_json(url: str, params: dict, headers: dict, provider: str, transport=None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, transport=transport) as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        raise SearchError(f"{provider} isn't reachable at {url} — is it running? ({exc})") from exc
    if response.status_code == 401:
        raise SearchError(f"{provider} rejected the request — check its API key in .env.")
    if response.status_code == 403:
        raise SearchError(f"{provider} refused JSON output — enable the json format in its settings.")
    if response.status_code != 200:
        raise SearchError(f"{provider} returned HTTP {response.status_code}.")
    try:
        return response.json()
    except ValueError as exc:
        raise SearchError(f"{provider} returned something that isn't JSON.") from exc


class DegoogProvider:
    """degoog's GET /api/search returns results already merged, scored and
    deduplicated across engines (degoog-org.github.io/docs/api.html)."""

    name = "degoog"

    def __init__(self, base_url: str, api_key: str = "", transport=None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = await _get_json(
            f"{self._base_url}/api/search",
            {"q": query, "type": "web"},
            headers,
            self.name,
            self._transport,
        )
        return [
            SearchResult(title=r.get("title") or r["url"], url=r["url"], snippet=r.get("snippet") or "")
            for r in payload.get("results", [])
            if r.get("url")
        ][:limit]


class SearxngProvider:
    """SearXNG only serves JSON once `json` is added to search.formats in its
    settings.yml — otherwise /search?format=json is a 403."""

    name = "searxng"

    def __init__(self, base_url: str, transport=None) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        payload = await _get_json(
            f"{self._base_url}/search",
            {"q": query, "format": "json"},
            {},
            self.name,
            self._transport,
        )
        return [
            SearchResult(title=r.get("title") or r["url"], url=r["url"], snippet=r.get("content") or "")
            for r in payload.get("results", [])
            if r.get("url")
        ][:limit]


def build_search_provider() -> SearchProvider:
    if settings.search_provider == "degoog":
        return DegoogProvider(settings.degoog_url, settings.degoog_api_key)
    if settings.search_provider == "searxng":
        return SearxngProvider(settings.searxng_url)
    raise ValueError(
        f"Unknown search_provider '{settings.search_provider}' — expected 'degoog' or 'searxng'."
    )
