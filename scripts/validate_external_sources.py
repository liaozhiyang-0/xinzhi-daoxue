from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.services.scenario_catalog import ScenarioCatalog  # noqa: E402

KNOWN_SOURCE_TYPES = {"academic_paper", "web_page", "user_source"}
KNOWN_CREDENTIAL_MODES = {"none", "optional_api_key", "required_api_key"}


def _public_http_url(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty URL")
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field} must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{field} must not contain credentials or query parameters")
    return url


def validate() -> dict[str, object]:
    path = ROOT / "config" / "external_sources.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if raw.get("version") != "1.0":
        raise ValueError("external source registry version must be 1.0")
    sources = raw.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("external source registry must contain sources")

    seen_ids: set[str] = set()
    source_types: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ValueError("each external source must be an object")
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError("each external source needs a non-empty id")
        if source_id in seen_ids:
            raise ValueError(f"duplicate external source id: {source_id}")
        seen_ids.add(source_id)
        source_type = source.get("source_type")
        if source_type not in KNOWN_SOURCE_TYPES:
            raise ValueError(f"{source_id}: unsupported source_type={source_type}")
        source_types.add(str(source_type))
        if source.get("scope") != "academic":
            raise ValueError(f"{source_id}: current registry expects academic scope")
        _public_http_url(
            source.get("default_base_url"), field=f"{source_id}.default_base_url"
        )
        _public_http_url(
            source.get("official_docs_url"), field=f"{source_id}.official_docs_url"
        )
        credential_mode = source.get("credential_mode")
        if credential_mode not in KNOWN_CREDENTIAL_MODES:
            raise ValueError(
                f"{source_id}: unsupported credential_mode={credential_mode}"
            )
        if credential_mode != "none" and not source.get("credential_env"):
            raise ValueError(
                f"{source_id}: credential_env required for credentialed source"
            )
        if source.get("metadata_only_by_default") is not True:
            raise ValueError(f"{source_id}: metadata_only_by_default must be true")
        if source.get("manual_review_required") is not True:
            raise ValueError(f"{source_id}: manual_review_required must be true")

    catalog = ScenarioCatalog(ROOT / "config" / "scenarios.yaml")
    externally_supported = 0
    for scenario in catalog.list(enabled_only=False):
        policy_types = set(scenario.evidence_policy.authoritative_source_types) | set(
            scenario.evidence_policy.supplemental_source_types
        )
        if policy_types & source_types or "external_reference" in policy_types:
            externally_supported += 1
    if externally_supported != len(catalog.list(enabled_only=False)):
        raise ValueError("not every scenario declares an external evidence path")

    return {
        "valid": True,
        "registry_version": raw["version"],
        "source_count": len(sources),
        "source_types": sorted(source_types),
        "scenarios_with_external_path": externally_supported,
        "metadata_only_by_default": True,
        "manual_review_required": True,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
