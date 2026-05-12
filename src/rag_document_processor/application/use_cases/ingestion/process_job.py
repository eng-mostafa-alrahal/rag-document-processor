from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_document_processor.application.ports.blob_storage import IBlobStorage
from rag_document_processor.application.ports.embedding_pipeline import IEmbeddingPipeline
from rag_document_processor.application.ports.embedding_sink import IEmbeddingSink
from rag_document_processor.application.ports.repositories import IJobRepository
from rag_document_processor.application.ports.text_extractor import ITextExtractor
from rag_document_processor.application.ports.url_fetcher import IUrlFetcher
from rag_document_processor.core.config import Settings
from rag_document_processor.domain.entities.job import JobStatus, SourceKind
from rag_document_processor.domain.exceptions import UnsupportedMimeTypeError
from rag_document_processor.infrastructure.db.repositories.job_repo import SqlJobRepository

log = logging.getLogger(__name__)


def _normalize_ctype(ctype: str | None) -> str:
    return (ctype or "application/octet-stream").split(";")[0].strip().lower()


class ProcessIngestionJobUseCase:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        blob_storage: IBlobStorage,
        url_fetcher: IUrlFetcher,
        text_extractor: ITextExtractor,
        pipeline: IEmbeddingPipeline,
        sink: IEmbeddingSink,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._blobs = blob_storage
        self._urls = url_fetcher
        self._extractor = text_extractor
        self._pipeline = pipeline
        self._sink = sink
        self._settings = settings

    async def execute(self, job_id: str) -> None:
        jid = UUID(job_id)
        async with self._session_factory() as session:
            jobs: IJobRepository = SqlJobRepository(session)
            job = await jobs.get_by_id(jid)
            if job is None:
                log.warning("job_missing", extra={"job_id": job_id})
                return
            if job.status == JobStatus.COMPLETED:
                return
            user_id = job.user_id
            source_kind = job.source_kind
            blob_key = job.blob_key
            source_url = job.source_url
            source_text = job.source_text
            content_type = job.content_type
            original_filename = job.original_filename
            await jobs.update_status(jid, status=JobStatus.PROCESSING, error_message=None)
            await session.commit()

        try:
            await self._sink.clear(jid, user_id)

            if source_kind == SourceKind.TEXT:
                raw_text = source_text or ""
            elif source_kind == SourceKind.URL:
                if not source_url:
                    raise ValueError("URL job missing source_url")
                body, ctype = await self._urls.fetch(source_url)
                ctype_norm = _normalize_ctype(ctype)
                if ctype_norm == "application/octet-stream" and body.startswith(b"%PDF"):
                    ctype_norm = "application/pdf"
                allowed = self._settings.allowed_mime_set | {"text/plain", "text/markdown"}
                if ctype_norm not in allowed:
                    raise UnsupportedMimeTypeError(f"URL content type not allowed: {ctype_norm}")
                raw_text = await self._extractor.extract(
                    body,
                    content_type=ctype_norm,
                    filename=source_url.rsplit("/", maxsplit=1)[-1] or None,
                )
            else:
                if not blob_key:
                    raise ValueError("File job missing blob_key")
                body = await self._blobs.get_bytes(blob_key)
                raw_text = await self._extractor.extract(
                    body, content_type=content_type, filename=original_filename
                )

            meta = {"job_id": str(jid), "source_kind": source_kind.value}
            chunks = 0
            async for chunk in self._pipeline.process(raw_text, metadata=meta):
                await self._sink.emit(jid, user_id, chunk)
                chunks += 1

            await self._sink.finalize(jid, user_id, metadata={"chunks": str(chunks)})

            async with self._session_factory() as session:
                jobs = SqlJobRepository(session)
                await jobs.increment_chunks(jid, chunks)
                await jobs.update_status(jid, status=JobStatus.COMPLETED)
                await session.commit()
        except Exception as e:
            log.exception("job_failed", extra={"job_id": job_id})
            async with self._session_factory() as session:
                jobs = SqlJobRepository(session)
                await jobs.update_status(jid, status=JobStatus.FAILED, error_message=str(e))
                await session.commit()
