def test_file_upload_uses_local_fallback(client, tmp_path) -> None:
    response = client.post(
        "/api/v1/files",
        files={"upload": ("note.txt", b"safe text", "text/plain")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["filename"] == "note.txt"
    assert payload["size_bytes"] == 9
    assert payload["storage_key"].startswith("local:")


def test_file_upload_rejects_mismatched_type(client) -> None:
    response = client.post(
        "/api/v1/files",
        files={"upload": ("note.txt", b"not an image", "image/png")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
