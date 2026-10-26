"""The researcher's entire toolset: web_search and read_url, nothing else.

This dispatch table *is* the read-only guarantee. A researcher's LLM can ask
for write_file or delete_directory all it likes — there's no entry for it
here, so the call comes back "Unknown tool" and nothing happens.

Every page read is recorded as a source (blackboard research_sources) and
its extracted text stored on disk, content-addressed, under
research_dir/pages/ — so the report's citations can be checked later
against exactly what the researcher saw.

Every call is also logged, one line each, prefixed "[research] <name>" —
hope.log, and so the dashboard's log card, shows the run as it happens.
"""

import asyncio
import hashlib
import json
from pathlib import Path

from loguru import logger

from memory.coordination.store import Blackboard
from tools.web import fetch
from tools.web.fetch import FetchBlocked, as_untrusted
from tools.web.search import SearchError, SearchProvider

_SEARCH_LIMIT = 8

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web. Returns titles, URLs and short snippets — read a page before citing it.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The search query."}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Read the main text of one public web page.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "An http(s) URL."}},
                "required": ["url"],
            },
        },
    },
]


class ResearchToolbox:
    def __init__(
        self,
        search_provider: SearchProvider,
        blackboard: Blackboard,
        run_id: str,
        agent_id: str,
        pages_dir: Path,
        read_url=fetch.read_url,
        label: str | None = None,
    ) -> None:
        self._search = search_provider
        self._blackboard = blackboard
        self._run_id = run_id
        self._agent_id = agent_id
        self._pages_dir = pages_dir
        self._read_url = read_url
        self._label = label or agent_id
        self.pages_read: list[tuple[str, str]] = []  # (title, url), for voice mode mid-run

    async def dispatch(self, name: str, arguments: str) -> str:
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return "Tool arguments weren't valid JSON."
        if name == "web_search":
            return await self.web_search(str(args.get("query", "")))
        if name == "read_url":
            return await self.read_url(str(args.get("url", "")))
        return f"Unknown tool: {name}"

    async def web_search(self, query: str) -> str:
        if not query.strip():
            return "Empty query."
        logger.info(f'[research] {self._label} searching: "{query}"')
        try:
            results = await self._search.search(query, _SEARCH_LIMIT)
        except SearchError as exc:
            logger.warning(f"[research] {self._label} search failed: {exc}")
            return str(exc)
        logger.info(f"[research] {self._label} got {len(results)} results")
        if not results:
            return "No results."
        lines = [f"{i}. {r.title}\n   {r.url}\n   {r.snippet}" for i, r in enumerate(results, 1)]
        return as_untrusted(f"search: {query}", "\n".join(lines))

    async def read_url(self, url: str) -> str:
        logger.info(f"[research] {self._label} reading: {url}")
        try:
            page = await self._read_url(url)
        except FetchBlocked as exc:
            logger.warning(f"[research] {self._label} blocked: {exc}")
            return str(exc)
        except Exception as exc:  # network errors of every flavour — tell the agent, keep going
            logger.warning(f"[research] {self._label} couldn't read {url}: {exc}")
            return f"Couldn't read {url}: {exc}"
        if not page.text.strip():
            logger.info(f"[research] {self._label} read {url}: no readable text")
            return f"{url} had no readable text (it may need JavaScript)."
        logger.info(
            f'[research] {self._label} read "{page.title}" '
            f"({len(page.text)} chars{', truncated' if page.truncated else ''})"
        )

        await self._record(page.url, page.title, page.text)
        note = "\n[truncated — the page was longer]" if page.truncated else ""
        return as_untrusted(page.url, f"Title: {page.title}\n\n{page.text}{note}")

    async def _record(self, url: str, title: str, text: str) -> None:
        """Best-effort: a failed write loses the audit trail for one page,
        never the research itself."""
        self.pages_read.append((title, url))
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        try:
            await asyncio.to_thread(self._store_page, content_hash, text)
            await asyncio.to_thread(
                self._blackboard.add_source, self._run_id, self._agent_id, url, title, content_hash
            )
        except Exception:
            logger.exception(f"Couldn't record research source {url}")

    def _store_page(self, content_hash: str, text: str) -> None:
        path = self._pages_dir / f"{content_hash}.txt"
        if path.exists():
            return
        self._pages_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
