from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Literal

import networkx as nx

from app.circuit.contracts import (
    OUTPUT_PORT_NAMES,
    PORT_CONTRACTS,
    SUPPORTED_COMPONENT_TYPES,
    CircuitIR,
    ValidationIssue,
    ValidationReport,
    ValidationState,
)


def validate_circuit(circuit: CircuitIR) -> ValidationReport:
    """Run deterministic topology checks without circuit simulation."""

    started = perf_counter()
    issues: list[ValidationIssue] = []
    warnings: list[str] = []
    component_ids = [component.id for component in circuit.components]
    net_ids = [net.id for net in circuit.nets]
    known_nets = set(net_ids)

    for duplicate in _duplicates(component_ids):
        issues.append(
            ValidationIssue(
                code="duplicate_component_id",
                message=f"重复元件 id: {duplicate}",
                component_id=duplicate,
            )
        )
    for duplicate in _duplicates(net_ids):
        issues.append(
            ValidationIssue(
                code="duplicate_net_id",
                message=f"重复网络 id: {duplicate}",
                net_id=duplicate,
            )
        )

    graph: nx.Graph = nx.Graph()
    for component in circuit.components:
        node = f"component:{component.id}"
        graph.add_node(node, kind="component")
        if component.type not in SUPPORTED_COMPONENT_TYPES:
            issues.append(
                ValidationIssue(
                    code="invalid_component_type",
                    message=f"不支持的元件类型: {component.type}",
                    component_id=component.id,
                )
            )
            continue
        required, optional = PORT_CONTRACTS[component.type]
        missing = required - set(component.ports)
        for port in sorted(missing):
            issues.append(
                ValidationIssue(
                    code="required_port_missing",
                    message=f"元件 {component.id} 缺少端口 {port}",
                    component_id=component.id,
                )
            )
        allowed = required | optional
        for port in sorted(set(component.ports) - allowed):
            issues.append(
                ValidationIssue(
                    code="invalid_port",
                    message=f"元件 {component.id} 不支持端口 {port}",
                    component_id=component.id,
                )
            )
        seen_nets: dict[str, str] = {}
        for port, net_id in component.ports.items():
            if net_id not in known_nets:
                issues.append(
                    ValidationIssue(
                        code="invalid_net_ref",
                        message=f"端口 {component.id}.{port} 引用未知网络 {net_id}",
                        component_id=component.id,
                        net_id=net_id,
                    )
                )
            if net_id in seen_nets:
                allowed_power_join = component.type == "opamp" and {
                    seen_nets[net_id],
                    port,
                } <= {"plus", "minus", "vplus", "vminus"}
                if not allowed_power_join:
                    issues.append(
                        ValidationIssue(
                            code="self_connection",
                            message=(
                                f"元件 {component.id} 的端口 "
                                f"{seen_nets[net_id]} 和 {port} 同接网络 {net_id}"
                            ),
                            component_id=component.id,
                            net_id=net_id,
                        )
                    )
            seen_nets[net_id] = port
            net_node = f"net:{net_id}"
            graph.add_node(net_node, kind="net")
            graph.add_edge(node, net_node, port=port)
        if not component.ports:
            issues.append(
                ValidationIssue(
                    code="floating_component",
                    message=f"元件 {component.id} 没有连接端口",
                    component_id=component.id,
                )
            )

    for net in circuit.nets:
        graph.add_node(f"net:{net.id}", kind="net")

    component_ports_by_net: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for component in circuit.components:
        for port, net_id in component.ports.items():
            component_ports_by_net[net_id].append((component.id, port))
    for net_id, ports in component_ports_by_net.items():
        output_ports = [
            (component_id, port)
            for component_id, port in ports
            if port in OUTPUT_PORT_NAMES
        ]
        if len(output_ports) > 1:
            issues.append(
                ValidationIssue(
                    code="obvious_output_output_short",
                    message=f"网络 {net_id} 连接多个输出端口",
                    severity="warning",
                    net_id=net_id,
                )
            )
        if len(ports) == 1:
            component_id, _ = ports[0]
            issues.append(
                ValidationIssue(
                    code="floating_component",
                    message=f"元件 {component_id} 在网络 {net_id} 上没有拓扑伙伴",
                    severity="warning",
                    component_id=component_id,
                    net_id=net_id,
                )
            )

    if graph.number_of_nodes() and not nx.is_connected(graph):
        issues.append(
            ValidationIssue(code="disconnected_graph", message="电路拓扑包含不连通子图")
        )

    for uncertainty in circuit.uncertainties:
        if uncertainty.severity == "critical" and (
            uncertainty.component_ids or uncertainty.net_ids
        ):
            warnings.append(f"critical_uncertainty:{uncertainty.id}")
        elif uncertainty.severity != "info":
            warnings.append(f"uncertainty:{uncertainty.id}")

    has_errors = any(issue.severity == "error" for issue in issues)
    has_critical_uncertainty = bool(
        warnings and any(item.startswith("critical_uncertainty:") for item in warnings)
    )
    status: ValidationState = (
        "invalid"
        if has_errors
        else "uncertain"
        if has_critical_uncertainty
        else "validated"
    )
    schema_error_codes = {
        "duplicate_component_id",
        "duplicate_net_id",
        "invalid_component_type",
        "required_port_missing",
        "invalid_port",
        "invalid_net_ref",
    }
    schema_status: Literal["validated", "invalid"] = (
        "invalid"
        if any(issue.code in schema_error_codes for issue in issues)
        else "validated"
    )
    topology_status: Literal["validated", "invalid", "uncertain"] = (
        "invalid"
        if any(
            issue.code in {"self_connection", "disconnected_graph"}
            and issue.severity == "error"
            for issue in issues
        )
        else "uncertain"
        if any(issue.code == "floating_component" for issue in issues)
        else "validated"
    )
    semantic_status: Literal["validated", "partially_validated", "needs_review"] = (
        "needs_review"
        if has_critical_uncertainty
        else "partially_validated"
        if warnings
        else "validated"
    )
    report = ValidationReport(
        status=status,
        issues=issues,
        warnings=warnings,
        latency_ms=(perf_counter() - started) * 1000,
        schema_status=schema_status,
        topology_status=topology_status,
        semantic_status=semantic_status,
    )
    circuit.validation_state = status
    return report


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates
