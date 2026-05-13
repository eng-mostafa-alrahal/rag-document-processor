class DomainError(Exception):
    """Base for domain-level errors."""


class InvalidCredentialsError(DomainError):
    pass


class UserAlreadyExistsError(DomainError):
    pass


class UserInactiveError(DomainError):
    pass


class InvalidRefreshTokenError(DomainError):
    pass


class FileTooLargeError(DomainError):
    pass


class UnsupportedMimeTypeError(DomainError):
    pass


class InvalidLlamaParseTierError(DomainError):
    pass


class UrlFetchError(DomainError):
    pass


class JobNotFoundError(DomainError):
    pass


class ForbiddenJobAccessError(DomainError):
    pass
