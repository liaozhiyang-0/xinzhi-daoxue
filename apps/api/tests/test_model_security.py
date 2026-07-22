from app.core.redaction import redact_sensitive_text


def test_model_log_redaction_hides_keys_and_images() -> None:
    value = redact_sensitive_text(
        "Authorization: Bearer abc.123 DASHSCOPE_API_KEY=secret "
        "data:image/png;base64,AAAABBBB"
    )

    assert "abc.123" not in value
    assert "secret" not in value
    assert "AAAABBBB" not in value
    assert "[REDACTED" in value
