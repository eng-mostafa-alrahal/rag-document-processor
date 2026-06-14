from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Human-readable label for the client/key.")


class ApiKeyCreatedResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    api_key: str = Field(description="The full secret key. Shown only once \u2014 store it securely.")
    created_at: str


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    created_at: str
    last_used_at: str | None
