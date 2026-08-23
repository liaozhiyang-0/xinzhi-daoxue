"""Package controlled Runtime E2E artifacts into offline release evidence.

The E2E runner deliberately captures only the redacted API projection. That is
safe for browser debugging but omits ``state_data`` and cannot prove replay
integrity. This offline tool reads an operator-provided isolated SQLite DB,
exports the exact top-level Runtime checkpoint trace, rejects unsafe input, and
uses the existing provider-free collector to build one suite per Agent.

It never starts an API, calls a Provider/tool/model, changes launch modes, or
works against a network database. Structural suites still require independent
semantic review and a human release decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # type: ignore[import-untyped]  # noqa: E402
    RuntimeCanarySuite,
    audit_checkpoint_trace,
)
from app.runtime.semantic_evidence import payload_sha256  # noqa: E402

from scripts.collect_runtime_canary import build_suite_from_manifest  # noqa: E402

SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "raw_prompt",
        "secret",
        "token",
        "uid",
    }
)
PAIRED_INPUT_SCHEMA_VERSION = "runtime_paired_input.v1"
ATTACHMENT_FIELDS = (
    "filename",
    "content_type",
    "size_bytes",
    "checksum_sha256",
)


@dataclass(frozen=True, slots=True)
class PairArtifact:
    agent_id: str
    case_id: str
    legacy_input: Path
    legacy_task: Path
    runtime_input: Path
    runtime_task: Path
    runtime_task_id: str
    legacy_audit: dict[str, Any]
    runtime_audit: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RuntimeTrace:
    records: list[dict[str, Any]]
    run_id: str
    agent_version: str
    plan_version: str
    captured_at: datetime


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def _stable_attachments(value: object, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{label}.attachments must be a list")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValueError(f"{label}.attachments[{index}] must be an object")
        result.append(
            {
                key: item.get(key)
                for key in ATTACHMENT_FIELDS
                if key in item
            }
        )
    return result


def _runtime_request_from_task_input(
    input_content: Mapping[str, Any], *, label: str
) -> dict[str, Any]:
    options = input_content.get("options")
    if not isinstance(options, Mapping):
        return {}
    requests = [
        value.get("request")
        for value in options.values()
        if isinstance(value, Mapping) and isinstance(value.get("request"), Mapping)
    ]
    if len(requests) > 1:
        raise ValueError(f"{label}: multiple Runtime request payloads found")
    request = requests[0] if requests else None
    return dict(request) if isinstance(request, Mapping) else {}


def _stable_input_from_task(
    task: Mapping[str, Any],
    *,
    label: str,
    runtime_request_override: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_content = task.get("input_content")
    if not isinstance(input_content, Mapping):
        raise ValueError(f"{label}: input_content is missing")
    canonical_input = input_content.get("canonical_input")
    if not isinstance(canonical_input, Mapping):
        raise ValueError(f"{label}: canonical_input is missing")
    runtime_request = _runtime_request_from_task_input(input_content, label=label)
    if runtime_request_override is not None:
        runtime_request = dict(runtime_request_override)
    return {
        "schema_version": PAIRED_INPUT_SCHEMA_VERSION,
        "course_id": str(input_content.get("course_id", "")),
        "intent": str(input_content.get("intent", "")),
        "canonical_input": dict(canonical_input),
        "attachments": _stable_attachments(
            input_content.get("attachments", []), label=label
        ),
        "runtime_request": runtime_request,
    }


def _validate_task_audit(
    task: Mapping[str, Any],
    *,
    label: str,
    runtime_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    input_content = task.get("input_content")
    if not isinstance(input_content, Mapping):
        raise ValueError(f"{label}: input_content is missing")
    options = input_content.get("options")
    audit = options.get("_audit") if isinstance(options, Mapping) else None
    if not isinstance(audit, Mapping):
        raise ValueError(f"{label}: task_audit.v1 is missing")
    if audit.get("schema_version") != "task_audit.v1":
        raise ValueError(f"{label}: task_audit schema version is invalid")
    if "runtime_request_sha256" not in audit:
        raise ValueError(f"{label}: task_audit Runtime request hash is missing")
    if str(audit.get("task_id", "")) != str(task.get("id", "")):
        raise ValueError(f"{label}: task_audit task identity mismatch")
    if str(audit.get("agent_id", "")) != str(task.get("agent_id", "")):
        raise ValueError(f"{label}: task_audit Agent identity mismatch")
    if audit.get("input_sha256") != payload_sha256(
        dict(input_content["canonical_input"])
    ):
        raise ValueError(f"{label}: task_audit input hash mismatch")
    raw_attachments = input_content.get("attachments", [])
    _stable_attachments(raw_attachments, label=label)
    if not str(audit.get("attachment_sha256", "")):
        raise ValueError(f"{label}: task_audit attachment hash is missing")
    if str(audit.get("terminal_status", "")) != str(task.get("status", "")):
        raise ValueError(f"{label}: task_audit terminal status mismatch")
    failure_category = str(task.get("failure_category") or "")
    if str(audit.get("failure_category", "")) != failure_category:
        raise ValueError(f"{label}: task_audit failure category mismatch")
    if not isinstance(raw_attachments, list):
        raise ValueError(f"{label}: attachments must be a list")
    audit_attachments = [
        {
            "file_id": item.get("file_id"),
            "checksum_sha256": item.get("checksum_sha256") or "",
            "content_type": item.get("content_type"),
            "size_bytes": item.get("size_bytes"),
        }
        for item in raw_attachments
        if isinstance(item, Mapping)
    ]
    if audit.get("attachment_sha256") != payload_sha256(audit_attachments):
        raise ValueError(f"{label}: task_audit attachment hash mismatch")
    runtime_request_hash = str(audit.get("runtime_request_sha256", ""))
    if runtime_request_hash:
        if runtime_request is None:
            raise ValueError(f"{label}: Runtime request payload is missing")
        if runtime_request_hash != payload_sha256(dict(runtime_request)):
            raise ValueError(f"{label}: task_audit Runtime request hash mismatch")
    return dict(audit)


def _structural_task_payload(task: Mapping[str, Any], *, label: str) -> dict[str, Any]:
    """Keep canary parity fields while excluding the original task input."""

    payload = {
        key: task[key]
        for key in (
            "id",
            "agent_id",
            "status",
            "provider",
            "failure_category",
            "result_content",
        )
        if key in task
    }
    result_content = payload.get("result_content")
    if not isinstance(result_content, Mapping):
        raise ValueError(f"{label}: result_content must be an object")
    sensitive_paths = _sensitive_key_paths(result_content)
    if sensitive_paths:
        raise ValueError(
            f"{label}: result_content contains sensitive keys: "
            + ",".join(sorted(sensitive_paths))
        )
    return payload


def _validate_final_output(
    task: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    label: str,
) -> None:
    """Require a terminal result to carry the same user-facing display contract."""

    if str(task.get("status", "")) != "completed":
        return
    result_content = task.get("result_content")
    if not isinstance(result_content, Mapping):
        raise ValueError(f"{label}: completed task result_content is missing")
    structured = result_content.get("structured_result")
    if not isinstance(structured, Mapping):
        raise ValueError(f"{label}: completed task structured_result is missing")
    presentation = structured.get("presentation")
    if not isinstance(presentation, Mapping):
        raise ValueError(f"{label}: final presentation is missing")
    required_presentation_fields = (
        "title",
        "status_label",
        "provider_label",
        "evidence_message",
    )
    if any(
        not str(presentation.get(field, "")).strip()
        for field in required_presentation_fields
    ):
        raise ValueError(f"{label}: final presentation is incomplete")
    scenario_id = str(audit.get("scenario_id", "")).strip()
    if not scenario_id:
        return
    if audit.get("output_contract_version") != "scenario_output_contract.v1":
        raise ValueError(f"{label}: scenario output contract version is missing")
    contract = structured.get("scenario_contract")
    if not isinstance(contract, Mapping):
        raise ValueError(f"{label}: scenario output contract is missing")
    if str(contract.get("scenario_id", "")) != scenario_id:
        raise ValueError(f"{label}: scenario output contract identity mismatch")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _require_contained(root: Path, path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"{label} is missing or outside the E2E output root") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} must be a regular file")
    return resolved


def _artifact_pairs(output_root: Path) -> list[PairArtifact]:
    artifact_root = output_root / "artifacts"
    if not artifact_root.is_dir():
        raise ValueError("E2E artifact directory is missing")
    pairs: list[PairArtifact] = []
    for runtime_task in sorted(artifact_root.rglob("runtime/task.json")):
        runtime_task = _require_contained(output_root, runtime_task, "runtime task")
        relative_parts = runtime_task.relative_to(artifact_root).parts
        if len(relative_parts) == 4:
            agent_name, base_case_id, runtime_name, task_name = relative_parts
            sample_name = ""
        elif len(relative_parts) == 5:
            agent_name, base_case_id, sample_name, runtime_name, task_name = (
                relative_parts
            )
        else:
            raise ValueError(
                "runtime task must use artifacts/<agent>/<case>/runtime or "
                "artifacts/<agent>/<case>/<sample>/runtime layout"
            )
        if runtime_name != "runtime" or task_name != "task.json":
            raise ValueError("runtime task has an invalid artifact layout")
        runtime_dir = runtime_task.parent
        mode_dir = runtime_dir.parent
        case_id = (
            f"{base_case_id}__{sample_name}" if sample_name else base_case_id
        )
        legacy_dir = mode_dir / "legacy"
        legacy_task = _require_contained(
            output_root, legacy_dir / "task.json", "legacy task"
        )
        runtime_input = _require_contained(
            output_root, runtime_dir / "input.json", "runtime input"
        )
        legacy_input = _require_contained(
            output_root, legacy_dir / "input.json", "legacy input"
        )
        runtime_payload = _read_json_object(runtime_task, "runtime task")
        legacy_payload = _read_json_object(legacy_task, "legacy task")
        agent_id = agent_name
        if runtime_payload.get("agent_id") != agent_id:
            raise ValueError(f"{case_id}: runtime task Agent identity mismatch")
        if legacy_payload.get("agent_id") != agent_id:
            raise ValueError(f"{case_id}: legacy task Agent identity mismatch")
        task_id = runtime_payload.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{case_id}: runtime task id is missing")
        runtime_input_payload = _read_json_object(runtime_input, "runtime input")
        legacy_input_payload = _read_json_object(legacy_input, "legacy input")
        if runtime_input_payload != legacy_input_payload:
            raise ValueError(f"{case_id}: Legacy and Runtime input payloads differ")
        paired_runtime_request = runtime_input_payload.get("runtime_request")
        if not isinstance(paired_runtime_request, Mapping):
            raise ValueError(f"{case_id}: paired Runtime request is invalid")
        expected_runtime_input = _stable_input_from_task(
            runtime_payload,
            label=f"{case_id}: Runtime task",
            runtime_request_override=paired_runtime_request,
        )
        expected_legacy_input = _stable_input_from_task(
            legacy_payload,
            label=f"{case_id}: Legacy task",
            runtime_request_override=paired_runtime_request,
        )
        if runtime_input_payload != expected_runtime_input:
            raise ValueError(f"{case_id}: Runtime input snapshot does not match task")
        if legacy_input_payload != expected_legacy_input:
            raise ValueError(f"{case_id}: Legacy input snapshot does not match task")
        legacy_audit = _validate_task_audit(
            legacy_payload,
            label=f"{case_id}: Legacy task",
            runtime_request=paired_runtime_request,
        )
        runtime_audit = _validate_task_audit(
            runtime_payload,
            label=f"{case_id}: Runtime task",
            runtime_request=paired_runtime_request,
        )
        _validate_final_output(
            legacy_payload, legacy_audit, label=f"{case_id}: Legacy task"
        )
        _validate_final_output(
            runtime_payload, runtime_audit, label=f"{case_id}: Runtime task"
        )
        pairs.append(
            PairArtifact(
                agent_id=agent_id,
                case_id=case_id,
                legacy_input=legacy_input,
                legacy_task=legacy_task,
                runtime_input=runtime_input,
                runtime_task=runtime_task,
                runtime_task_id=task_id,
                legacy_audit=legacy_audit,
                runtime_audit=runtime_audit,
            )
        )
    if not pairs:
        raise ValueError("no complete Legacy/Runtime pairs found under artifacts")
    return pairs


def _sqlite_uri(database: Path) -> str:
    try:
        resolved = database.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("checkpoint SQLite database is missing") from exc
    if not resolved.is_file():
        raise ValueError("checkpoint SQLite database must be a regular file")
    return f"{resolved.as_uri()}?mode=ro"


def _parse_state_data(raw: Any, *, sequence: int) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"checkpoint {sequence} state_data is invalid JSON"
            ) from exc
    else:
        value = raw
    if not isinstance(value, dict):
        raise ValueError(f"checkpoint {sequence} state_data must be a JSON object")
    return value


def _sensitive_key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, nested in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.casefold() in SENSITIVE_KEYS:
                paths.append(path)
            paths.extend(_sensitive_key_paths(nested, prefix=path))
        return paths
    if isinstance(value, list):
        return [
            nested_path
            for index, nested in enumerate(value)
            for nested_path in _sensitive_key_paths(nested, prefix=f"{prefix}[{index}]")
        ]
    return []


def _parse_captured_at(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "checkpoint created_at is not an ISO-8601 timestamp"
            ) from exc
    else:
        raise ValueError("checkpoint created_at is missing")
    # sqlite may drop the timezone marker; all repository checkpoints are UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _runtime_trace_from_sqlite(
    database: Path,
    *,
    task_id: str,
    expected_agent_id: str,
) -> RuntimeTrace:
    """Read exactly one top-level Runtime run and validate its raw trace."""

    try:
        with sqlite3.connect(_sqlite_uri(database), uri=True) as connection:
            connection.row_factory = sqlite3.Row
            runs = connection.execute(
                """
                SELECT id, agent_id, agent_version, plan_version
                FROM agent_runs
                WHERE task_id = ?
                  AND run_kind = 'runtime'
                  AND agent_id = ?
                  AND COALESCE(parent_run_id, '') = ''
                ORDER BY created_at DESC, id DESC
                """,
                (task_id, expected_agent_id),
            ).fetchall()
            if len(runs) != 1:
                raise ValueError(
                    f"{expected_agent_id}:{task_id}: expected exactly one "
                    f"top-level Runtime run, found {len(runs)}"
                )
            run = runs[0]
            rows = connection.execute(
                """
                SELECT sequence, state_version, state_data, event_sequence, created_at
                FROM agent_checkpoints
                WHERE run_id = ?
                ORDER BY sequence ASC
                """,
                (run["id"],),
            ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError(
            f"unable to read controlled checkpoint SQLite database: {exc}"
        ) from exc

    records: list[dict[str, Any]] = []
    captured_at: datetime | None = None
    for row in rows:
        sequence = int(row["sequence"])
        state_data = _parse_state_data(row["state_data"], sequence=sequence)
        sensitive_paths = _sensitive_key_paths(state_data)
        if sensitive_paths:
            raise ValueError(
                f"{expected_agent_id}:{task_id}: checkpoint contains sensitive keys: "
                + ",".join(sorted(sensitive_paths))
            )
        records.append(
            {
                "sequence": sequence,
                "state_version": int(row["state_version"]),
                "state_data": state_data,
                "event_sequence": int(row["event_sequence"]),
            }
        )
        captured_at = _parse_captured_at(row["created_at"])
    audit = audit_checkpoint_trace(records)
    if not audit.valid:
        raise ValueError(
            f"{expected_agent_id}:{task_id}: checkpoint audit failed: "
            + ",".join(audit.errors)
        )
    if audit.run_id != run["id"]:
        raise ValueError(
            f"{expected_agent_id}:{task_id}: checkpoint run identity mismatch"
        )
    if audit.agent_ids != [expected_agent_id]:
        raise ValueError(
            f"{expected_agent_id}:{task_id}: checkpoint Agent identity mismatch"
        )
    plan_version = str(run["plan_version"] or "").strip()
    if not plan_version or audit.plan_versions != [plan_version]:
        raise ValueError(
            f"{expected_agent_id}:{task_id}: checkpoint plan version mismatch"
        )
    agent_version = str(run["agent_version"] or "").strip()
    if not agent_version:
        raise ValueError(
            f"{expected_agent_id}:{task_id}: Runtime Agent version is missing"
        )
    if captured_at is None:
        raise ValueError(f"{expected_agent_id}:{task_id}: checkpoint trace is empty")
    return RuntimeTrace(
        records=records,
        run_id=str(run["id"]),
        agent_version=agent_version,
        plan_version=plan_version,
        captured_at=captured_at,
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "agent"


def _relative(root: Path, path: Path) -> str:
    return path.resolve(strict=True).relative_to(root).as_posix()


def _suite_id(prefix: str, agent_id: str, pairs: list[PairArtifact]) -> str:
    task_ids = ",".join(sorted(pair.runtime_task_id for pair in pairs))
    digest = hashlib.sha256(task_ids.encode("utf-8")).hexdigest()[:12]
    return f"{_slug(prefix)}-{_slug(agent_id)}-{digest}"


def _write_semantic_review_material(
    *,
    root: Path,
    agent_id: str,
    pairs: list[PairArtifact],
    suite: RuntimeCanarySuite,
    authorization_ref: str,
) -> tuple[Path, Path, Path]:
    """Create controlled reviewer inputs, paired outputs, and a blank template.

    The packet deliberately exposes only a review whitelist rather than whole
    Task records or Runtime state.  This gives a reviewer the paired answers
    needed for a semantic comparison without accidentally re-exporting Task
    metadata, provider details, or checkpoint state.  The blank template is
    intentionally not release evidence: every case remains ``needs_review``
    with an explicit incomplete reviewer marker.
    """

    inputs: dict[str, dict[str, Any]] = {}
    judgements: dict[str, dict[str, Any]] = {}
    pair_by_case_id = {pair.case_id: pair for pair in suite.pairs}
    review_cases: list[dict[str, Any]] = []
    for pair in sorted(pairs, key=lambda item: item.case_id):
        input_payload = _read_json_object(pair.runtime_input, "runtime input")
        input_sensitive_paths = _sensitive_key_paths(input_payload)
        if input_sensitive_paths:
            raise ValueError(
                f"{agent_id}:{pair.case_id}: input contains sensitive keys: "
                + ",".join(sorted(input_sensitive_paths))
            )
        suite_pair = pair_by_case_id.get(pair.case_id)
        if suite_pair is None:
            raise ValueError(
                f"{agent_id}:{pair.case_id}: structural suite pair is missing"
            )
        legacy_output = _reviewable_output(
            pair.legacy_task,
            label=f"{agent_id}:{pair.case_id}: Legacy task",
        )
        runtime_output = _reviewable_output(
            pair.runtime_task,
            label=f"{agent_id}:{pair.case_id}: Runtime task",
        )
        inputs[pair.case_id] = input_payload
        judgements[pair.case_id] = {
            "dimensions": {
                "task_fulfillment": None,
                "factual_correctness": None,
                "evidence_faithfulness": None,
                "safety": None,
            },
            "decision": "needs_review",
            "judge_type": "human",
            "rubric_version": "runtime-semantic-v1",
            "reviewer_ref": "TO_BE_COMPLETED_BY_INDEPENDENT_REVIEWER",
            "reviewed_at": "TO_BE_COMPLETED_WITH_ISO8601_TIMEZONE",
            "redaction_status": "redacted",
            "authorization_ref": authorization_ref,
        }
        review_cases.append(
            {
                "case_id": pair.case_id,
                "redacted_input": input_payload,
                "legacy_output": legacy_output,
                "runtime_output": runtime_output,
                "legacy_audit": _reviewable_audit(pair.legacy_audit),
                "runtime_audit": _reviewable_audit(pair.runtime_audit),
                "input_sha256": suite_pair.input_sha256,
                "legacy_payload_sha256": payload_sha256(suite_pair.legacy_payload),
                "runtime_payload_sha256": payload_sha256(suite_pair.runtime_payload),
                "runtime_checkpoint_path": _relative(
                    root, pair.runtime_task.parent / "checkpoints.json"
                ),
            }
        )
    slug = _slug(agent_id)
    inputs_path = root / "semantic_review_inputs" / f"{slug}.json"
    packet_path = root / "semantic_review_packets" / f"{slug}.json"
    template_path = root / "semantic_review_judgements_template" / f"{slug}.json"
    _write_json(inputs_path, inputs)
    _write_json(
        packet_path,
        {
            "schema_version": "runtime_semantic_review_packet.v1",
            "agent_id": agent_id,
            "runtime_plan_version": suite.evidence.runtime_plan_version,
            "authorization_ref": authorization_ref,
            "redaction_status": "redacted",
            "review_boundary": (
                "Paired output excerpts for semantic review only; this packet "
                "does not constitute an independent human review or release decision."
            ),
            "cases": review_cases,
        },
    )
    _write_json(template_path, judgements)
    return inputs_path, packet_path, template_path


def _reviewable_output(path: Path, *, label: str) -> dict[str, Any]:
    """Return the minimum paired-output projection needed for semantic review."""

    task = _read_json_object(path, label)
    result_content = task.get("result_content")
    if not isinstance(result_content, dict):
        raise ValueError(f"{label}: result_content must be a JSON object")
    sensitive_paths = _sensitive_key_paths(result_content)
    if sensitive_paths:
        raise ValueError(
            f"{label}: result_content contains sensitive keys: "
            + ",".join(sorted(sensitive_paths))
        )
    answer = result_content.get("answer")
    if not isinstance(answer, str):
        raise ValueError(f"{label}: result_content.answer must be a string")
    output: dict[str, Any] = {"status": task.get("status"), "answer": answer}
    for field in ("citations", "warnings"):
        if field in result_content:
            output[field] = result_content[field]
    structured = result_content.get("structured_result")
    if isinstance(structured, Mapping):
        for field in ("presentation", "scenario_contract", "math_content"):
            value = structured.get(field)
            if isinstance(value, Mapping):
                output[field] = dict(value)
    return output


def _reviewable_audit(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Expose only the redacted identity fields needed for reviewer binding."""

    return {
        key: audit.get(key)
        for key in (
            "schema_version",
            "task_id",
            "scenario_id",
            "run_batch_id",
            "input_sha256",
            "attachment_sha256",
            "runtime_request_sha256",
            "runtime_run_id",
            "evidence_ids",
            "artifact_ids",
            "output_contract_version",
            "terminal_status",
            "failure_category",
        )
    }


def package_e2e_evidence(
    *,
    output_root: Path,
    sqlite_database: Path,
    authorization_ref: str,
    suite_prefix: str = "authorized-dev-e2e",
) -> dict[str, Any]:
    """Export complete traces and build one structural suite per Agent."""

    if not authorization_ref.strip():
        raise ValueError("authorization_ref must be non-empty")
    try:
        root = output_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("E2E output root is missing") from exc
    if not root.is_dir():
        raise ValueError("E2E output root must be a directory")

    grouped: dict[str, list[PairArtifact]] = defaultdict(list)
    for pair in _artifact_pairs(root):
        grouped[pair.agent_id].append(pair)

    report_agents: list[dict[str, Any]] = []
    for agent_id, pairs in sorted(grouped.items()):
        case_ids = [
            pair.case_id for pair in sorted(pairs, key=lambda item: item.case_id)
        ]
        agent_report: dict[str, Any] = {
            "agent_id": agent_id,
            "case_ids": case_ids,
            "structural_release_eligible": False,
            "blocking_reasons": [],
        }
        try:
            traces: dict[str, RuntimeTrace] = {}
            structural_paths: dict[str, tuple[Path, Path]] = {}
            for pair in pairs:
                trace = _runtime_trace_from_sqlite(
                    sqlite_database,
                    task_id=pair.runtime_task_id,
                    expected_agent_id=agent_id,
                )
                if pair.runtime_audit.get("runtime_run_id") != trace.run_id:
                    raise ValueError(
                        f"{agent_id}:{pair.case_id}: task_audit Runtime run "
                        "identity mismatch"
                    )
                checkpoint_path = pair.runtime_task.parent / "checkpoints.json"
                _write_json(checkpoint_path, {"checkpoints": trace.records})
                traces[pair.case_id] = trace
                structural_root = (
                    root
                    / "structural_payloads"
                    / _slug(agent_id)
                    / _slug(pair.case_id)
                )
                legacy_structural_path = structural_root / "legacy.json"
                runtime_structural_path = structural_root / "runtime.json"
                _write_json(
                    legacy_structural_path,
                    _structural_task_payload(
                        _read_json_object(pair.legacy_task, "legacy task"),
                        label=f"{agent_id}:{pair.case_id}: Legacy task",
                    ),
                )
                _write_json(
                    runtime_structural_path,
                    _structural_task_payload(
                        _read_json_object(pair.runtime_task, "runtime task"),
                        label=f"{agent_id}:{pair.case_id}: Runtime task",
                    ),
                )
                structural_paths[pair.case_id] = (
                    legacy_structural_path,
                    runtime_structural_path,
                )

            agent_versions = {trace.agent_version for trace in traces.values()}
            plan_versions = {trace.plan_version for trace in traces.values()}
            if len(agent_versions) != 1 or len(plan_versions) != 1:
                raise ValueError(
                    "paired cases disagree on Agent or Runtime plan version"
                )
            captured_at = max(trace.captured_at for trace in traces.values())
            manifest_path = root / f"runtime_canary_manifest_{_slug(agent_id)}.json"
            manifest = {
                "schema_version": "runtime_canary_manifest.v2",
                "agent_id": agent_id,
                "agent_version": next(iter(agent_versions)),
                "runtime_plan_version": next(iter(plan_versions)),
                "suite_id": _suite_id(suite_prefix, agent_id, pairs),
                "authorization_ref": authorization_ref.strip(),
                "captured_at": captured_at.isoformat(),
                "cases": [
                    {
                        "case_id": pair.case_id,
                        "input": _relative(root, pair.runtime_input),
                        "legacy": _relative(
                            root, structural_paths[pair.case_id][0]
                        ),
                        "runtime": _relative(
                            root, structural_paths[pair.case_id][1]
                        ),
                        "checkpoints": _relative(
                            root, pair.runtime_task.parent / "checkpoints.json"
                        ),
                    }
                    for pair in sorted(pairs, key=lambda item: item.case_id)
                ],
            }
            _write_json(manifest_path, manifest)
            suite = build_suite_from_manifest(manifest_path)
            suite_path = root / "structural_suites" / f"{_slug(agent_id)}.json"
            _write_json(suite_path, suite.model_dump(mode="json"))
            semantic_inputs_path, semantic_packet_path, judgement_template_path = (
                _write_semantic_review_material(
                    root=root,
                    agent_id=agent_id,
                    pairs=pairs,
                    suite=suite,
                    authorization_ref=authorization_ref.strip(),
                )
            )
            agent_report.update(
                {
                    "agent_version": manifest["agent_version"],
                    "runtime_plan_version": manifest["runtime_plan_version"],
                    "manifest": _relative(root, manifest_path),
                    "structural_suite": _relative(root, suite_path),
                    "semantic_inputs": _relative(root, semantic_inputs_path),
                    "semantic_review_packet": _relative(root, semantic_packet_path),
                    "semantic_judgements_template": _relative(
                        root, judgement_template_path
                    ),
                    "structural_release_eligible": True,
                }
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            agent_report["blocking_reasons"] = [str(exc)]
        report_agents.append(agent_report)
    report = {
        "schema_version": "runtime_e2e_evidence_package.v1",
        "packaged_at": datetime.now(UTC).isoformat(),
        "authorization_ref": authorization_ref.strip(),
        "agents": report_agents,
        "semantic_review_required": True,
        "human_release_decision_required": True,
    }
    _write_json(root / "evidence_packaging_report.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Existing ignored runtime_authorized_dev_e2e output directory.",
    )
    parser.add_argument(
        "--checkpoint-sqlite",
        type=Path,
        required=True,
        help="Read-only isolated SQLite database used for this E2E run.",
    )
    parser.add_argument(
        "--authorization-ref",
        required=True,
        help="Operator authorization reference for the already-captured pairs.",
    )
    parser.add_argument("--suite-prefix", default="authorized-dev-e2e")
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = package_e2e_evidence(
        output_root=args.output,
        sqlite_database=args.checkpoint_sqlite,
        authorization_ref=args.authorization_ref,
        suite_prefix=args.suite_prefix,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(
        not all(agent["structural_release_eligible"] for agent in report["agents"])
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
