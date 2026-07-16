from pathlib import Path

from tests.test_xingchen_export_parser import write_fixture

from scripts.inspect_xingchen_workflow import inspect_workflow


def test_export_parser_does_not_publish_private_values(tmp_path: Path) -> None:
    source = tmp_path / "fixture.yml"
    output = tmp_path / "generated"
    write_fixture(source)
    inspect_workflow(source, output)
    published = "\n".join(
        path.read_text(encoding="utf-8") for path in output.iterdir()
    )
    assert "secret-app-id" not in published
    assert "internal-user" not in published
    assert "private prompt content" not in published
    assert "start-raw" not in published
    assert "$.appId" in published
