import logging

from app.core.logging import mask_sensitive_text, redact


def test_sensitive_values_are_masked(caplog) -> None:
    secret = "never-log-this-secret"
    message = f"api_key={secret} postgresql://user:{secret}@localhost/db"
    masked = mask_sensitive_text(message)
    assert secret not in masked
    assert "***" in masked

    with caplog.at_level(logging.INFO):
        logging.getLogger("test").info("payload=%s", redact({"token": secret}))
    assert secret not in caplog.text
