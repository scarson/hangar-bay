class ESIException(Exception):
    """Base exception for ESI client errors."""
    pass


class ESIRequestFailedError(ESIException):
    """Raised when an ESI request fails for reasons like network errors or non-2xx/304 status codes."""
    def __init__(self, status_code: int = 0, message: str = ""):
        self.status_code = status_code
        self.message = message
        # All ctor args go to BaseException verbatim so pickle/copy can
        # reconstruct via cls(*args) without corrupting attributes (B042).
        super().__init__(status_code, message)

    def __str__(self):
        return f"ESI request failed with status {self.status_code}: {self.message}"


class ESINotModifiedError(ESIException):
    """Raised specifically for a 304 Not Modified response."""
    pass
