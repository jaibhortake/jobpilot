class LlmError(Exception):
    pass


class RateLimited(LlmError):
    pass


class RequestTooLarge(LlmError):
    pass


class LlmUnavailable(LlmError):
    pass


class LlmBadOutput(LlmError):
    pass
