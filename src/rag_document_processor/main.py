from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from rag_document_processor.core.config import get_settings
from rag_document_processor.core.container import build_container
from rag_document_processor.core.logger import configure_logging
from rag_document_processor.presentation.api.v1.router import api_router
from rag_document_processor.presentation.exception_handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(json_logs=settings.env.lower() not in ("dev", "development"), log_level=settings.log_level)
    container = build_container(settings)
    app.state.container = container
    yield
    await container.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
