import pytest

from app.config import Settings


def test_openai_api_key_is_optional() -> None:
    settings = Settings(openai_api_key="")

    assert settings.openai_api_key is None


def test_openai_model_default_and_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    assert Settings(_env_file=None).openai_model == "gpt-6.1-terra"
    assert Settings(_env_file=None, openai_model="another-model").openai_model == "another-model"


def test_cors_defaults_to_local_frontend_only() -> None:
    settings = Settings(_env_file=None)  # the defaults, not this machine's .env

    assert settings.cors_origin_list == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_cors_rejects_wildcard_origins() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        Settings(cors_origins="*")


def test_max_upload_bytes_must_be_reasonable() -> None:
    assert Settings(max_upload_bytes=1024).max_upload_bytes == 1024

    with pytest.raises(ValueError, match="greater than zero"):
        Settings(max_upload_bytes=0)

    with pytest.raises(ValueError, match="25MB"):
        Settings(max_upload_bytes=30 * 1024 * 1024)


def test_openai_request_timeout_must_be_reasonable() -> None:
    assert Settings(openai_request_timeout_seconds=30).openai_request_timeout_seconds == 30

    with pytest.raises(ValueError, match="at least 5 seconds"):
        Settings(openai_request_timeout_seconds=1)

    with pytest.raises(ValueError, match="120 seconds"):
        Settings(openai_request_timeout_seconds=121)
