"""Public errors never contain credentials, response bodies or user messages."""


class LLMConfigurationError(ValueError):
    """Missing/invalid local configuration or missing permission for a live call."""


class LLMServiceError(RuntimeError):
    def __init__(self, code: str, retry_after: float | None = None):
        self.code = code
        self.retry_after = retry_after
        super().__init__(f"LLM service: {code}")
