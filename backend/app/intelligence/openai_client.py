from openai import OpenAI

from app.config import Settings, get_settings


class OpenAIIntegrationError(RuntimeError):
    """Base error for backend-only OpenAI integration failures."""


class MissingOpenAIKeyError(OpenAIIntegrationError):
    """Raised only when an OpenAI-backed analysis call is requested without a key."""


class OpenAIRequestError(OpenAIIntegrationError):
    """Raised when the OpenAI SDK returns or wraps an API failure."""


class InvalidOpenAIJSONError(OpenAIIntegrationError):
    """Raised when OpenAI output is not valid structured JSON for SalesIntel."""


def get_openai_client(settings: Settings | None = None) -> OpenAI:
    active_settings = settings or get_settings()
    if active_settings.openai_api_key is None:
        raise MissingOpenAIKeyError(
            "OpenAI analysis is not configured. Set OPENAI_API_KEY on the backend."
        )
    return OpenAI(api_key=active_settings.openai_api_key)
