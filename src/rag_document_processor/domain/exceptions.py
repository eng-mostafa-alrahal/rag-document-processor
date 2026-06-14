class DomainError(Exception):
    """Base for domain-level errors."""


class ApiKeyNotFoundError(DomainError):
    pass


class FileTooLargeError(DomainError):
    pass


class UnsupportedMimeTypeError(DomainError):
    pass


class InvalidLlamaParseTierError(DomainError):
    pass


class InvalidEmbeddingDimensionsError(DomainError):
    """Raised when `embedding_dimensions` does not match the resolved embedding model."""

    def __init__(self, message: str, *, payload: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.payload: dict[str, object] = dict(payload or {})


class InvalidIngestEmbeddingOptionsError(DomainError):
    """Invalid embedding_pipeline / macro_splitter / embedder_provider / model overrides for this deployment."""

    pass


class UrlFetchError(DomainError):
    pass


class JobNotFoundError(DomainError):
    pass


class JobResultsNotReadyError(DomainError):
    """Raised when ingestion results are not yet available (job still running)."""
