from fastapi import HTTPException, status


class AuditAssistantException(Exception):
    """Base application exception."""


class ResourceNotFoundError(AuditAssistantException):
    """Raised when a requested resource does not exist."""


def not_found_exception(resource: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found: {identifier}",
    )
