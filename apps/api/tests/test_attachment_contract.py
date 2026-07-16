from app.contracts import AttachmentRef


def test_attachment_ref_serialization() -> None:
    attachment = AttachmentRef(
        file_id="file-1",
        filename="diagram.png",
        content_type="image/png",
        size_bytes=12,
        storage_key="local:key",
        checksum_sha256="a" * 64,
    )
    restored = AttachmentRef.model_validate(attachment.model_dump(mode="json"))
    assert restored.provider_file_id is None
    assert restored.checksum_sha256 == "a" * 64
