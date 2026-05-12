from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from rag_document_processor.application.use_cases.auth.auth import (
    LoginUseCase,
    LogoutUseCase,
    RefreshTokenUseCase,
    RegisterUserUseCase,
)
from rag_document_processor.application.use_cases.ingestion.get_job_status import GetJobStatusUseCase
from rag_document_processor.application.use_cases.ingestion.submit import (
    SubmitFileIngestionUseCase,
    SubmitTextIngestionUseCase,
    SubmitUrlIngestionUseCase,
)
from rag_document_processor.core.container import Container
from rag_document_processor.domain.entities.user import User
from rag_document_processor.infrastructure.db.repositories.user_repo import SqlUserRepository


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    container = get_container(request)
    try:
        payload = container.jwt_service.decode_access(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    try:
        uid = UUID(str(payload["sub"]))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid subject") from exc
    async with container.session_factory() as session:
        repo = SqlUserRepository(session)
        user = await repo.get_by_id(uid)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def register_user_use_case(container: ContainerDep) -> RegisterUserUseCase:
    return RegisterUserUseCase(container.session_factory, container.password_hasher)


def login_use_case(container: ContainerDep) -> LoginUseCase:
    return LoginUseCase(container.session_factory, container.password_hasher, container.jwt_service)


def refresh_use_case(container: ContainerDep) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(container.session_factory, container.jwt_service, container.refresh_store)


def logout_use_case(container: ContainerDep) -> LogoutUseCase:
    return LogoutUseCase(container.jwt_service, container.refresh_store)


def submit_file_use_case(container: ContainerDep) -> SubmitFileIngestionUseCase:
    return SubmitFileIngestionUseCase(
        container.session_factory, container.blob_storage, container.task_queue, container.settings
    )


def submit_url_use_case(container: ContainerDep) -> SubmitUrlIngestionUseCase:
    return SubmitUrlIngestionUseCase(container.session_factory, container.task_queue)


def submit_text_use_case(container: ContainerDep) -> SubmitTextIngestionUseCase:
    return SubmitTextIngestionUseCase(container.session_factory, container.task_queue)


def get_job_status_use_case(container: ContainerDep) -> GetJobStatusUseCase:
    return GetJobStatusUseCase(container.session_factory)
