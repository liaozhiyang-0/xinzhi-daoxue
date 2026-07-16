import pytest
from app.core.errors import ValidationAppError
from app.services.storage import sanitize_filename


@pytest.mark.parametrize(
    "filename",
    ["../../secret.txt", r"..\secret.txt", "/tmp/secret.txt"],
)
def test_path_traversal_filename_is_rejected(filename: str) -> None:
    with pytest.raises(ValidationAppError):
        sanitize_filename(filename)
