from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SENSITIVE_KEYS = {
    "uid",
    "appid",
    "userid",
    "flowid",
    "spaceid",
    "repoid",
    "outerrepoid",
    "corerepoid",
    "pluginid",
    "apikey",
    "secret",
    "token",
}


@dataclass(frozen=True)
class PublicNode:
    public_id: str
    raw_id: str
    name: str
    node_type: str
    responsibility: str
    content_sha256: str | None
    content_size: int
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    parameters: dict[str, str]


def first_value(data: dict[str, Any], keys: tuple[str, ...], default: str) -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def find_named_list(value: Any, names: set[str]) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in names and isinstance(item, list):
                return [entry for entry in item if isinstance(entry, dict)]
        for item in value.values():
            found = find_named_list(item, names)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_named_list(item, names)
            if found:
                return found
    return []


def sensitive_paths(value: Any, prefix: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key.lower().replace("_", "") in SENSITIVE_KEYS and item not in (
                None,
                "",
            ):
                paths.append(path)
            paths.extend(sensitive_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(sensitive_paths(item, f"{prefix}[{index}]"))
    return paths


def private_content(node: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in node.items():
        lowered = key.lower()
        if any(word in lowered for word in ("prompt", "code", "script")):
            if isinstance(value, str):
                parts.append(value)
            else:
                parts.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts)


def variable_names(value: Any) -> tuple[str, ...]:
    names: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"name", "variable", "key", "field"} and isinstance(
                item, str
            ):
                names.add(item)
            else:
                names.update(variable_names(item))
    elif isinstance(value, list):
        for item in value:
            names.update(variable_names(item))
    elif isinstance(value, str):
        names.add(value)
    return tuple(sorted(name for name in names if len(name) <= 100))


def node_variables(
    node: dict[str, Any], keys: tuple[str, ...]
) -> tuple[str, ...]:
    for key in keys:
        if key in node:
            return variable_names(node[key])
    return ()


def safe_parameters(node: dict[str, Any]) -> dict[str, str]:
    allowed = {
        "temperature",
        "top_p",
        "top_k",
        "max_tokens",
        "maxTokens",
        "frequency_penalty",
        "presence_penalty",
    }
    result: dict[str, str] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in allowed and isinstance(item, (str, int, float, bool)):
                    result[key] = str(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(node)
    return result


def make_nodes(raw_nodes: list[dict[str, Any]]) -> list[PublicNode]:
    result: list[PublicNode] = []
    for index, node in enumerate(raw_nodes, start=1):
        raw_id = first_value(node, ("id", "nodeId", "node_id"), f"raw-{index}")
        name = first_value(
            node,
            ("name", "title", "displayName", "display_name", "label"),
            f"未命名节点 {index}",
        )
        node_type = first_value(
            node, ("type", "nodeType", "node_type", "kind"), "unknown"
        )
        description = first_value(
            node, ("description", "desc", "summary"), f"{name}（{node_type}）"
        )
        content = private_content(node)
        digest = (
            hashlib.sha256(content.encode("utf-8")).hexdigest() if content else None
        )
        result.append(
            PublicNode(
                public_id=f"N{index:03d}",
                raw_id=raw_id,
                name=name,
                node_type=node_type,
                responsibility=description[:240],
                content_sha256=digest,
                content_size=len(content),
                inputs=node_variables(
                    node,
                    ("inputs", "input", "inputVariables", "input_variables"),
                ),
                outputs=node_variables(
                    node,
                    ("outputs", "output", "outputVariables", "output_variables"),
                ),
                parameters=safe_parameters(node),
            )
        )
    return result


def edge_end(edge: dict[str, Any], keys: tuple[str, ...]) -> str:
    return first_value(edge, keys, "")


def public_edges(
    raw_edges: list[dict[str, Any]], nodes: list[PublicNode]
) -> list[tuple[str, str]]:
    mapping = {node.raw_id: node.public_id for node in nodes}
    result: list[tuple[str, str]] = []
    for edge in raw_edges:
        source = edge_end(
            edge, ("source", "sourceId", "source_id", "from", "fromNode")
        )
        target = edge_end(
            edge, ("target", "targetId", "target_id", "to", "toNode")
        )
        if source in mapping and target in mapping:
            result.append((mapping[source], mapping[target]))
    return result


def cycle_nodes(
    nodes: list[PublicNode], edges: list[tuple[str, str]]
) -> list[str]:
    graph: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        graph[source].append(target)
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            cycles.add(node_id)
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for target in graph[node_id]:
            visit(target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node in nodes:
        visit(node.public_id)
    return sorted(cycles)


def markdown_table(nodes: list[PublicNode]) -> str:
    lines = [
        "# SOLVER_CT 脱敏节点清单",
        "",
        (
            "| 公开 ID | 名称 | 类型 | 输入变量 | 输出变量 | 非敏感参数 | "
            "职责摘要 | 私有内容摘要 | 字符数 |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for node in nodes:
        digest = node.content_sha256 or "-"
        lines.append(
            f"| {node.public_id} | {node.name} | {node.node_type} | "
            f"{', '.join(node.inputs) or '-'} | {', '.join(node.outputs) or '-'} | "
            f"{json.dumps(node.parameters, ensure_ascii=False) or '-'} | "
            f"{node.responsibility} | {digest} | {node.content_size} |"
        )
    return "\n".join(lines) + "\n"


def typed_inventory(
    title: str, nodes: list[PublicNode], keywords: tuple[str, ...]
) -> str:
    matched = [
        node
        for node in nodes
        if any(keyword in node.node_type.lower() for keyword in keywords)
    ]
    lines = [f"# {title}", ""]
    if not matched:
        lines.append("未在导出结构中识别到对应节点。")
    else:
        for node in matched:
            lines.append(f"- `{node.public_id}` {node.name}（{node.node_type}）")
    return "\n".join(lines) + "\n"


def inspect_workflow(source: Path, output_dir: Path) -> dict[str, Any]:
    raw = source.read_bytes()
    try:
        document = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"YAML 解析失败: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("工作流 YAML 顶层必须是对象")

    raw_nodes = find_named_list(document, {"nodes", "node_list", "nodelist"})
    raw_edges = find_named_list(
        document, {"edges", "links", "connections", "edge_list", "edgelist"}
    )
    nodes = make_nodes(raw_nodes)
    edges = public_edges(raw_edges, nodes)
    counts = Counter(node.node_type for node in nodes)
    incoming = Counter(target for _, target in edges)
    outgoing = Counter(source for source, _ in edges)
    starts = [
        node.public_id
        for node in nodes
        if "start" in node.node_type.lower() or "开始" in node.name
    ]
    ends = [
        node.public_id
        for node in nodes
        if "end" in node.node_type.lower() or "结束" in node.name
    ]
    isolated = [
        node.public_id
        for node in nodes
        if incoming[node.public_id] == 0 and outgoing[node.public_id] == 0
    ]
    abnormal_no_in = [
        node.public_id
        for node in nodes
        if incoming[node.public_id] == 0 and node.public_id not in starts
    ]
    abnormal_no_out = [
        node.public_id
        for node in nodes
        if outgoing[node.public_id] == 0 and node.public_id not in ends
    ]
    cycles = cycle_nodes(nodes, edges)
    name = first_value(
        document,
        ("name", "workflowName", "workflow_name", "displayName"),
        source.stem,
    )
    dsl_version = first_value(
        document, ("dslVersion", "dsl_version", "version"), "unknown"
    )
    manifest = {
        "workflow_name": name,
        "dsl_version": dsl_version,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_types": dict(sorted(counts.items())),
        "redaction": "public summaries only; raw prompt/code/resource IDs omitted",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "solver_ct_export_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "solver_ct_node_inventory.md").write_text(
        markdown_table(nodes), encoding="utf-8"
    )
    graph = ["flowchart TD"]
    for node in nodes:
        safe_name = node.name.replace('"', "'")
        graph.append(f'  {node.public_id}["{safe_name}"]')
    for source_id, target_id in edges:
        graph.append(f"  {source_id} --> {target_id}")
    (output_dir / "solver_ct_graph.mmd").write_text(
        "\n".join(graph) + "\n", encoding="utf-8"
    )
    io_lines = [
        "# SOLVER_CT I/O 合同",
        "",
        "## 用户提供的冻结输入（待 YAML 独立核验）",
        "",
        "- `AGENT_USER_INPUT`: 文本，必填",
        "- `USER_INPUT_image`: 图片文件，选填",
        "- `USER_INPUT_pdf`: PDF 文件数组，选填",
        "",
        "## 用户提供的冻结输出（待 YAML 独立核验）",
        "",
        "- `output`: string，来自 `final_response_text`",
        "",
        f"识别到的开始节点：{', '.join(starts) or '无'}",
        f"识别到的结束节点：{', '.join(ends) or '无'}",
    ]
    for node in nodes:
        if node.public_id in starts:
            io_lines.append(
                f"- {node.public_id} 开始节点输入：{', '.join(node.inputs) or '未识别'}"
            )
        if node.public_id in ends:
            io_lines.append(
                f"- {node.public_id} 结束节点输出："
                f"{', '.join(node.outputs) or '未识别'}"
            )
    (output_dir / "solver_ct_io_contract.md").write_text(
        "\n".join(io_lines) + "\n", encoding="utf-8"
    )
    inventories = {
        "solver_ct_model_inventory.md": (
            "模型显示清单",
            ("llm", "model", "大模型"),
        ),
        "solver_ct_tool_inventory.md": ("工具显示清单", ("tool", "工具")),
        "solver_ct_knowledge_inventory.md": (
            "知识库显示清单",
            ("knowledge", "retrieval", "知识库"),
        ),
        "solver_ct_branch_inventory.md": (
            "分支器清单",
            ("branch", "condition", "router", "分支"),
        ),
    }
    for filename, (title, keywords) in inventories.items():
        (output_dir / filename).write_text(
            typed_inventory(title, nodes, keywords), encoding="utf-8"
        )
    integrity = [
        "# SOLVER_CT 完整性报告",
        "",
        f"- 节点数：{len(nodes)}",
        f"- 连线数：{len(edges)}",
        f"- 孤立节点：{', '.join(isolated) or '无'}",
        f"- 异常无入边节点：{', '.join(abnormal_no_in) or '无'}",
        f"- 异常无出边节点：{', '.join(abnormal_no_out) or '无'}",
        f"- 检测到的循环入口：{', '.join(cycles) or '无'}",
    ]
    (output_dir / "solver_ct_integrity_report.md").write_text(
        "\n".join(integrity) + "\n", encoding="utf-8"
    )
    paths = sensitive_paths(document)
    sensitive = [
        "# SOLVER_CT 敏感字段报告",
        "",
        "仅记录字段路径，不输出原始值。",
        "",
        *[f"- `{path}`" for path in paths],
    ]
    if not paths:
        sensitive.append("- 未发现已知敏感字段。")
    (output_dir / "solver_ct_sensitive_field_report.md").write_text(
        "\n".join(sensitive) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="脱敏检查星辰工作流 YAML")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.is_file():
        print(f"BLOCKED: input YAML not found: {args.input}")
        return 2
    try:
        manifest = inspect_workflow(args.input, args.output_dir)
    except ValueError as exc:
        print(str(exc))
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
