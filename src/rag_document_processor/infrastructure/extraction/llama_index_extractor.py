from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from rag_document_processor.application.ports.text_extractor import ITextExtractor
from rag_document_processor.domain.exceptions import UnsupportedMimeTypeError


class LlamaIndexTextExtractor(ITextExtractor):
    """Extract plain text from supported binary formats using llama-index readers."""

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

        def _load_pdf(path: Path) -> str:
            from llama_index.readers.file import PDFReader

            docs = PDFReader().load_data(file_path=str(path))
            return "\n\n".join(d.text for d in docs)

        def _load_docx(path: Path) -> str:
            from llama_index.readers.file import DocxReader

            docs = DocxReader().load_data(file_path=str(path))
            return "\n\n".join(d.text for d in docs)

        if ctype == "application/pdf" or suffix == ".pdf":
            loader = _load_pdf
        elif (
            ctype
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or suffix == ".docx"
        ):
            loader = _load_docx
        else:
            raise UnsupportedMimeTypeError(f"Unsupported content type for extraction: {content_type}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".bin") as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        try:
            return await asyncio.to_thread(loader, tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
