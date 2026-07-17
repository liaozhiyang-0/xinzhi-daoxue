from hashlib import sha256


def test_file_upload_uses_local_fallback(client) -> None:
    data = b"safe text"
    response = client.post(
        "/api/v1/files",
        files={"upload": ("note.txt", data, "text/plain")},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "note.txt"
    assert payload["size_bytes"] == len(data)
    assert payload["storage_key"].startswith("local:")
    assert payload["checksum_sha256"] == sha256(data).hexdigest()


def test_file_upload_rejects_empty_and_mismatched_type(client) -> None:
    empty = client.post(
        "/api/v1/files",
        files={"upload": ("empty.txt", b"", "text/plain")},
    )
    mismatch = client.post(
        "/api/v1/files",
        files={"upload": ("note.txt", b"text", "image/png")},
    )
    assert empty.status_code == 422
    assert mismatch.status_code == 422
