"""Project-specific exceptions."""


class LexiMaskError(Exception):
    """Base exception for LexiMask failures."""


class ValidationError(LexiMaskError):
    """Raised when input validation fails."""


class ConflictError(LexiMaskError):
    """Raised when the plan contains blocking conflicts."""


class MetadataError(LexiMaskError):
    """Raised when sidecar metadata is missing or inconsistent."""
