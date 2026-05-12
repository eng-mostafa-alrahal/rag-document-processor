from __future__ import annotations

import mimetypes
from urllib.parse import urlparse

import httpx

from rag_document_processor.application.ports.url_fetcher import IUrlFetcher
from rag_document_processor.core.config import Settings
from rag_document_processor.domain.exceptions import FileTooLargeError, UrlFetchError


class HttpUrlFetcher(IUrlFetcher):
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, url: str) -> tuple[bytes, str | None]:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise UrlFetchError("Only http(s) URLs are allowed")
        try:
            async with self._client.stream("GET", url, follow_redirects=True, timeout=60.0) as resp:
                resp.raise_for_status()
                cl = resp.headers.get("content-length")
                if cl and int(cl) > self._settings.max_url_fetch_bytes:
                    raise FileTooLargeError("URL response too large")
                chunks: list[bytes] = []
                total = 0
                async for part in resp.aiter_bytes():
                    total += len(part)
                    if total > self._settings.max_url_fetch_bytes:
                        raise FileTooLargeError("URL response too large")
                    chunks.append(part)
                body = b"".join(chunks)
                ctype = resp.headers.get("content-type")
                if ctype:
                    ctype = ctype.split(";")[0].strip()
                return body, ctype
        except FileTooLargeError:
            raise
        except httpx.HTTPError as e:
            raise UrlFetchError(str(e)) from e
