from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from rag_document_processor.application.use_cases.api_keys.manage import (
    CreateApiKeyUseCase,
    ListApiKeysUseCase,
    RevokeApiKeyUseCase,
)
from rag_document_processor.application.use_cases.ingestion.get_job_results import GetJobResultsUseCase
from rag_document_processor.application.use_cases.ingestion.get_job_status import GetJobStatusUseCase
from rag_document_processor.application.use_cases.ingestion.submit import (
    SubmitFileIngestionUseCase,
    SubmitTextIngestionUseCase,
    SubmitUrlIngestionUseCase,
)
from rag_document_processor.core.container import Container
from rag_document_processor.domain.entities.api_key import ApiKey
from rag_document_processor.infrastructure.db.repositories.api_key_repo import SqlApiKeyRepository
from rag_document_processor.infrastructure.security.api_key_hashing import hash_api_key


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]

_api_key_header = APIKeyHeader(name="X-API-Key", scheme_name="X-API-Key", auto_error=False)
_admin_secret_header = APIKeyHeader(
    name="X-Admin-Secret", scheme_name="X-Admin-Secret", auto_error=False
)


async def require_api_key(
    request: Request,
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> ApiKey:
    if not api_key or not api_key.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    container = get_container(request)
    key_hash = hash_api_key(api_key)
    async with container.session_factory() as session:
        repo = SqlApiKeyRepository(session)
        key = await repo.get_active_by_hash(key_hash)
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        await repo.touch_last_used(key.id)
        await session.commit()
    return key


ApiKeyDep = Annotated[ApiKey, Depends(require_api_key)]


async def require_admin(
    request: Request,
    admin_secret: Annotated[str | None, Security(_admin_secret_header)],
) -> None:
    configured = get_container(request).settings.api_key_admin_secret
    if not configured or not admin_secret or not secrets.compare_digest(admin_secret, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin secret")


AdminGuard = Depends(require_admin)


def create_api_key_use_case(container: ContainerDep) -> CreateApiKeyUseCase:
    return CreateApiKeyUseCase(container.session_factory)


def list_api_keys_use_case(container: ContainerDep) -> ListApiKeysUseCase:
    return ListApiKeysUseCase(container.session_factory)


def revoke_api_key_use_case(container: ContainerDep) -> RevokeApiKeyUseCase:
    return RevokeApiKeyUseCase(container.session_factory)


def submit_file_use_case(container: ContainerDep) -> SubmitFileIngestionUseCase:
    return SubmitFileIngestionUseCase(
        container.session_factory, container.blob_storage, container.task_queue, container.settings
    )


def submit_url_use_case(container: ContainerDep) -> SubmitUrlIngestionUseCase:
    return SubmitUrlIngestionUseCase(container.session_factory, container.task_queue, container.settings)


def submit_text_use_case(container: ContainerDep) -> SubmitTextIngestionUseCase:
    return SubmitTextIngestionUseCase(container.session_factory, container.task_queue, container.settings)


def get_job_status_use_case(container: ContainerDep) -> GetJobStatusUseCase:
    return GetJobStatusUseCase(container.session_factory, container.settings)


def get_job_results_use_case(container: ContainerDep) -> GetJobResultsUseCase:
    return GetJobResultsUseCase(
        container.session_factory, container.ingestion_result_reader, container.settings
    )
