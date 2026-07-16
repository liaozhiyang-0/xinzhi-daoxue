import json
from pathlib import Path

from scripts.export_openapi import export_openapi


def test_openapi_is_generated_from_application(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    export_openapi(output)
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert schema["paths"]["/api/v1/tasks"]["post"]["responses"]["202"]
    assert "/api/v1/tasks/{task_id}/stream" in schema["paths"]
    assert "/debug" in schema["paths"]
