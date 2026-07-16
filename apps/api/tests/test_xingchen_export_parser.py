from pathlib import Path

from scripts.inspect_xingchen_workflow import inspect_workflow


def write_fixture(path: Path) -> None:
    path.write_text(
        """
name: fixture-workflow
version: "1"
appId: secret-app-id
nodes:
  - id: start-raw
    name: 开始
    type: start
  - id: llm-raw
    name: 解题模型
    type: llm
    prompt: private prompt content
    userId: internal-user
  - id: end-raw
    name: 结束
    type: end
edges:
  - source: start-raw
    target: llm-raw
  - source: llm-raw
    target: end-raw
""".strip(),
        encoding="utf-8",
    )


def test_export_parser_generates_inventory(tmp_path: Path) -> None:
    source = tmp_path / "fixture.yml"
    output = tmp_path / "generated"
    write_fixture(source)
    manifest = inspect_workflow(source, output)
    assert manifest["node_count"] == 3
    assert manifest["edge_count"] == 2
    assert len(manifest["source_sha256"]) == 64
    assert (output / "solver_ct_graph.mmd").exists()
    assert (output / "solver_ct_integrity_report.md").exists()
