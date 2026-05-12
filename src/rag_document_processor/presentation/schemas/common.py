from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    detail: str
    code: str


class HealthResponse(BaseModel):
    status: str = "ok"
