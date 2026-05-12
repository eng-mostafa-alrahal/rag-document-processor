from __future__ import annotations

from fastapi import APIRouter, Depends

from rag_document_processor.presentation.deps import (
    login_use_case,
    logout_use_case,
    refresh_use_case,
    register_user_use_case,
)
from rag_document_processor.presentation.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(body: RegisterRequest, uc=Depends(register_user_use_case)) -> UserResponse:
    dto = await uc.execute(email=body.email, password=body.password)
    return UserResponse(id=dto.id, email=dto.email)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, uc=Depends(login_use_case)) -> TokenResponse:
    tokens = await uc.execute(email=body.email, password=body.password)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, uc=Depends(refresh_use_case)) -> TokenResponse:
    tokens = await uc.execute(refresh_token=body.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post("/logout", status_code=204)
async def logout(body: LogoutRequest, uc=Depends(logout_use_case)) -> None:
    await uc.execute(refresh_token=body.refresh_token)
