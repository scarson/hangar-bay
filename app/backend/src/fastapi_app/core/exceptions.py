class ESIException(Exception):
    """Base exception for ESI client errors."""
    pass

class ESIRequestFailedError(ESIException):
    """Raised when an ESI request fails for reasons like network errors or non-2xx/304 status codes."""
    def __init__(self, status_code: int = 0, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"ESI request failed with status {status_code}: {message}")

class ESINotModifiedError(ESIException):
    """Raised specifically for a 304 Not Modified response."""
    pass
