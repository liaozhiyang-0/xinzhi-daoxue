def test_file_metadata_endpoint(client) -> None:
    uploaded = client.post(
        "/api/v1/files",
        files={"upload": ("note.md", b"# test", "text/markdown")},
    ).json()
    response = client.get(f"/api/v1/files/{uploaded['id']}")
    assert response.status_code == 200
    assert response.json() == uploaded


def test_missing_file_metadata_is_404(client) -> None:
    response = client.get("/api/v1/files/file-missing")
    assert response.status_code == 404
