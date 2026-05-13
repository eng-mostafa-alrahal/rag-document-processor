from __future__ import annotations

from pathlib import Path

from rag_document_processor.application.ports.text_extractor import ITextExtractor
from rag_document_processor.core.config import Settings


def _default_upload_name(*, ctype: str, suffix: str, filename: str | None) -> str:
    if filename:
        return filename
    if suffix in (".pdf", ".docx"):
        return f"document{suffix}"
    if ctype == "application/pdf":
        return "document.pdf"
    if ctype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return "document.docx"
    return "document.bin"


def _parse_response_to_text(result: object) -> str:
    """Turn a ParsingGetResponse into a single string (markdown preferred)."""
    parts: list[str] = []
    markdown = getattr(result, "markdown", None)
    if markdown is not None:
        pages = sorted(markdown.pages, key=lambda p: p.page_number)
        for page in pages:
            if not page.success:
                continue
            body = page.markdown
            if page.header:
                body = f"{page.header}\n\n{body}"
            if page.footer:
                body = f"{body}\n\n{page.footer}"
            parts.append(body)
        if parts:
            return "\n\n".join(parts)

    text = getattr(result, "text", None)
    if text is not None and text.pages:
        ordered = sorted(text.pages, key=lambda p: p.page_number)
        return "\n\n".join(p.text for p in ordered)

    return ""


class LlamaCloudParseExtractor(ITextExtractor):
    """LlamaParse via LlamaCloud for PDF/DOCX; plain text inline; other types delegated."""

    def __init__(self, *, settings: Settings, fallback: ITextExtractor) -> None:
        self._settings = settings
        self._fallback = fallback

    def _uses_cloud_parse(self, ctype: str, suffix: str) -> bool:
        return bool(self._settings.llama_cloud_api_key) and (
            ctype == "application/pdf"
            or suffix == ".pdf"
            or ctype
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or suffix == ".docx"
        )

    async def extract(
        self,
        data: bytes,
        *,
        content_type: str | None,
        filename: str | None,
        llama_parse_tier: str | None = None,
    ) -> str:
        ctype = (content_type or "").split(";")[0].strip().lower()
        suffix = Path(filename or "").suffix.lower()

        if ctype in ("text/plain", "text/markdown") or suffix in (".txt", ".md"):
            return data.decode("utf-8", errors="replace")

        if not self._uses_cloud_parse(ctype, suffix):
            return await self._fallback.extract(
                data,
                content_type=content_type,
                filename=filename,
                llama_parse_tier=llama_parse_tier,
            )

        from llama_cloud import AsyncLlamaCloud

        name = _default_upload_name(ctype=ctype, suffix=suffix, filename=filename)
        upload_ctype = ctype or (
            "application/pdf" if suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if suffix == ".docx"
            else "application/octet-stream"
        )
        upload_file: tuple[str | None, bytes, str | None] = (name, data, upload_ctype)

        tier = llama_parse_tier or self._settings.llama_parse_tier
        client = AsyncLlamaCloud(api_key=self._settings.llama_cloud_api_key)
        # FAST tier does not support markdown expansion (LlamaCloud returns 400).
        expand = ["text"] if str(tier).strip().lower() == "fast" else ["markdown", "text"]
        try:
            result = await client.parsing.parse(
                upload_file=upload_file,
                tier=tier,
                version="latest",
                expand=expand,
            )
        finally:
            await client.close()

        text = _parse_response_to_text(result)
        if not text.strip():
            raise RuntimeError("LlamaCloud parse returned no text or markdown content")
        return text
