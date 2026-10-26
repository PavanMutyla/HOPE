"""Read-only page fetcher for agents.

Every rule below is enforced here in code, because the thing on the other
end of the request is untrusted: a page can contain text written to steer
an agent ("now open http://localhost:3000/..."). Prompt instructions alone
don't hold against that.

- GET only. No cookies (a fresh client per call), no auth headers, no forms.
- http/https only, and the host must resolve to *public* addresses only —
  localhost, private ranges, link-local and the like are refused. This
  machine runs degoog, the Reflex dashboard and possibly other local
  services; none of them is reachable through this function.
- Redirects are followed by hand, at most _MAX_REDIRECTS, and every hop is
  re-checked — an allowed public URL redirecting to 127.0.0.1 is refused.
- Size, time and content-type caps, then trafilatura strips nav/ads/boilerplate.

Known gap: the address check and the connection are two separate DNS
lookups, so a hostile DNS server could answer differently the second time
(DNS rebinding). Closing that needs connecting to the checked IP directly
with SNI pinned, which httpx doesn't offer out of the box — revisit if
agents ever get anything beyond read access.
"""

import asyncio
import ipaddress
import socket
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura
from pydantic import BaseModel

_TIMEOUT_SECONDS = 15.0
_MAX_REDIRECTS = 5
_MAX_BYTES = 2_000_000
_MAX_CHARS = 24_000  # ~6k tokens — page text costs far more than the search itself
_ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_USER_AGENT = "Mozilla/5.0 (compatible; HOPE-research/0.1; read-only)"

Resolver = Callable[[str], Awaitable[list[str]]]


class FetchBlocked(ValueError):
    """The URL was refused by policy, not by the network. str(exc) is meant
    to go straight back to the agent."""


class PageText(BaseModel):
    url: str
    title: str
    text: str
    truncated: bool


async def _resolve(host: str) -> list[str]:
    infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    return sorted({info[4][0] for info in infos})


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


async def check_url(url: str, resolve: Resolver = _resolve) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchBlocked(f"Only http and https pages can be read, not '{parts.scheme}:'.")
    if not parts.hostname:
        raise FetchBlocked(f"'{url}' has no host.")
    try:
        addresses = await resolve(parts.hostname)
    except OSError as exc:
        raise FetchBlocked(f"Couldn't resolve {parts.hostname}: {exc}") from exc
    if not addresses or not all(_is_public(a) for a in addresses):
        raise FetchBlocked(
            f"{parts.hostname} points at a local or private address — agents may only read public websites."
        )


def _extract(body: str, content_type: str, url: str) -> tuple[str, str]:
    if content_type.startswith("text/plain"):
        return url, body
    text = trafilatura.extract(body, url=url, include_comments=False, favor_precision=True) or ""
    metadata = trafilatura.extract_metadata(body, default_url=url)
    title = (metadata.title if metadata and metadata.title else "") or url
    return title, text


async def read_url(url: str, resolve: Resolver = _resolve, transport=None) -> PageText:
    async with httpx.AsyncClient(
        timeout=_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": _USER_AGENT},
        transport=transport,
    ) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            await check_url(url, resolve)
            async with client.stream("GET", url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchBlocked(f"{url} redirected without saying where.")
                    url = urljoin(url, location)
                    continue
                if response.status_code != 200:
                    raise FetchBlocked(f"{url} returned HTTP {response.status_code}.")
                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith(_ALLOWED_TYPES):
                    raise FetchBlocked(f"{url} is '{content_type or 'unknown'}', not a readable web page.")
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > _MAX_BYTES:
                        break
                body = raw[:_MAX_BYTES].decode(response.encoding or "utf-8", errors="replace")
                break
        else:
            raise FetchBlocked(f"Too many redirects (more than {_MAX_REDIRECTS}).")

    title, text = await asyncio.to_thread(_extract, body, content_type, url)
    truncated = len(text) > _MAX_CHARS
    return PageText(url=url, title=title, text=text[:_MAX_CHARS], truncated=truncated)


def as_untrusted(source: str, text: str) -> str:
    """Wrap web-derived text before it reaches any agent's context, so every
    prompt can say: whatever is inside these tags is data, never instructions.
    A page that contains the closing tag itself would otherwise break out of
    the wrapper, so it's defanged first."""
    text = text.replace("</untrusted_web_content", "</ untrusted_web_content")
    source = source.replace('"', "%22")
    return f'<untrusted_web_content source="{source}">\n{text}\n</untrusted_web_content>'
