"""
Contract tests for web search providers (tools/web/search.py).

Every provider must turn its engine's JSON into SearchResult objects, honour
the result limit, skip entries with no URL, and turn every failure into a
SearchError whose message an agent can act on. To add a provider, subclass
SearchContractBase and describe its endpoint and response shape.
"""

import httpx
import pytest

from tools.web.search import DegoogProvider, SearchError, SearxngProvider, SearchResult


class SearchContractBase:
    """Subclasses set: provider_cls, base_url, path, snippet_key, and make_provider()."""

    base_url = "http://localhost:9999"

    def make_provider(self, transport):
        raise NotImplementedError

    def _results_payload(self, n: int) -> dict:
        return {"results": [
            {"title": f"T{i}", "url": f"https://site{i}.org", self.snippet_key: f"S{i}"}
            for i in range(n)
        ]}

    def _transport(self, response: httpx.Response, seen: list | None = None):
        def handler(request: httpx.Request) -> httpx.Response:
            if seen is not None:
                seen.append(request)
            return response
        return httpx.MockTransport(handler)

    @pytest.mark.contract
    async def test_returns_search_results(self):
        provider = self.make_provider(self._transport(httpx.Response(200, json=self._results_payload(2))))
        results = await provider.search("kokoro voices")
        assert results == [
            SearchResult(title="T0", url="https://site0.org", snippet="S0"),
            SearchResult(title="T1", url="https://site1.org", snippet="S1"),
        ]

    @pytest.mark.contract
    async def test_sends_query_to_the_documented_endpoint(self):
        seen: list[httpx.Request] = []
        provider = self.make_provider(self._transport(httpx.Response(200, json={"results": []}), seen))
        await provider.search("kokoro voices")
        assert seen[0].url.path == self.path
        assert seen[0].url.params["q"] == "kokoro voices"

    @pytest.mark.contract
    async def test_honours_limit(self):
        provider = self.make_provider(self._transport(httpx.Response(200, json=self._results_payload(10))))
        assert len(await provider.search("q", limit=3)) == 3

    @pytest.mark.contract
    async def test_skips_results_without_url(self):
        payload = {"results": [{"title": "no url"}, {"title": "ok", "url": "https://ok.org"}]}
        provider = self.make_provider(self._transport(httpx.Response(200, json=payload)))
        assert [r.url for r in await provider.search("q")] == ["https://ok.org"]

    @pytest.mark.contract
    async def test_missing_title_falls_back_to_url(self):
        payload = {"results": [{"url": "https://ok.org"}]}
        provider = self.make_provider(self._transport(httpx.Response(200, json=payload)))
        assert (await provider.search("q"))[0].title == "https://ok.org"

    @pytest.mark.contract
    @pytest.mark.parametrize("status", [401, 403, 500])
    async def test_http_errors_become_search_errors(self, status):
        provider = self.make_provider(self._transport(httpx.Response(status)))
        with pytest.raises(SearchError):
            await provider.search("q")

    @pytest.mark.contract
    async def test_non_json_becomes_search_error(self):
        provider = self.make_provider(self._transport(httpx.Response(200, text="<html>")))
        with pytest.raises(SearchError):
            await provider.search("q")

    @pytest.mark.contract
    async def test_unreachable_instance_says_so(self):
        def refuse(request):
            raise httpx.ConnectError("connection refused")
        provider = self.make_provider(httpx.MockTransport(refuse))
        with pytest.raises(SearchError, match="is it running"):
            await provider.search("q")


class TestDegoogContract(SearchContractBase):
    path = "/api/search"
    snippet_key = "snippet"

    def make_provider(self, transport):
        return DegoogProvider(self.base_url, transport=transport)

    @pytest.mark.contract
    async def test_api_key_is_sent_as_bearer_token(self):
        seen: list[httpx.Request] = []
        provider = DegoogProvider(
            self.base_url, api_key="k3y",
            transport=self._transport(httpx.Response(200, json={"results": []}), seen),
        )
        await provider.search("q")
        assert seen[0].headers["authorization"] == "Bearer k3y"

    @pytest.mark.contract
    async def test_no_auth_header_without_api_key(self):
        seen: list[httpx.Request] = []
        await self.make_provider(self._transport(httpx.Response(200, json={"results": []}), seen)).search("q")
        assert "authorization" not in seen[0].headers


class TestSearxngContract(SearchContractBase):
    path = "/search"
    snippet_key = "content"

    def make_provider(self, transport):
        return SearxngProvider(self.base_url, transport=transport)

    @pytest.mark.contract
    async def test_requests_json_format(self):
        seen: list[httpx.Request] = []
        await self.make_provider(self._transport(httpx.Response(200, json={"results": []}), seen)).search("q")
        assert seen[0].url.params["format"] == "json"


@pytest.mark.contract
def test_build_search_provider_picks_configured_provider(monkeypatch):
    from settings import settings
    from tools.web.search import build_search_provider

    monkeypatch.setattr(settings, "search_provider", "searxng")
    assert isinstance(build_search_provider(), SearxngProvider)
    monkeypatch.setattr(settings, "search_provider", "degoog")
    assert isinstance(build_search_provider(), DegoogProvider)


@pytest.mark.contract
def test_build_search_provider_rejects_unknown_provider(monkeypatch):
    from settings import settings
    from tools.web.search import build_search_provider

    monkeypatch.setattr(settings, "search_provider", "google")
    with pytest.raises(ValueError):
        build_search_provider()
