from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Path, status

from rag_document_processor.presentation.deps import (
    AdminGuard,
    create_api_key_use_case,
    list_api_keys_use_case,
    revoke_api_key_use_case,
)
from rag_document_processor.presentation.schemas.api_keys import (
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    CreateApiKeyRequest,
)

router = APIRouter(prefix="/api-keys", tags=["api-keys"], dependencies=[AdminGuard])


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyRequest,
    uc=Depends(create_api_key_use_case),
) -> ApiKeyCreatedResponse:
    """Mint a new API key (admin only via `X-Admin-Secret`).

    The full `api_key` is returned **once**; only its hash is stored. Clients
    authenticate to ingest/jobs endpoints with the `X-API-Key` header.
    """
    dto = await uc.execute(name=body.name)
    return ApiKeyCreatedResponse(
        id=dto.id,
        name=dto.name,
        key_prefix=dto.key_prefix,
        api_key=dto.api_key,
        created_at=dto.created_at,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(uc=Depends(list_api_keys_use_case)) -> list[ApiKeyResponse]:
    """List all API keys (admin only). Secrets are never returned."""
    rows = await uc.execute()
    return [
        ApiKeyResponse(
            id=r.id,
            name=r.name,
            key_prefix=r.key_prefix,
            is_active=r.is_active,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
        )
        for r in rows
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID = Path(..., description="Identifier of the API key to revoke."),
    uc=Depends(revoke_api_key_use_case),
) -> None:
    """Revoke (deactivate) an API key (admin only)."""
    await uc.execute(key_id=key_id)
