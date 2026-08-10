"""Version-bound human authorization for Runtime launch promotion."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RELEASE_AUTHORIZATION_SCHEMA_VERSION = "runtime_release_authorization.v1"


class RuntimeReleaseAuthorization(BaseModel):
    """One approved launch-mode promotion for one Runtime Agent version."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["runtime_release_authorization.v1"] = (
        "runtime_release_authorization.v1"
    )
    agent_id: str = Field(min_length=1, max_length=160)
    suite_id: str = Field(min_length=1, max_length=160)
    agent_version: str = Field(min_length=1, max_length=64)
    runtime_plan_version: str = Field(min_length=1, max_length=64)
    launch_mode: Literal["canary", "default"]
    authorization_ref: str = Field(min_length=1, max_length=240)
    approver_ref: str = Field(min_length=1, max_length=240)
    approved_at: datetime
    status: Literal["approved", "revoked"] = "approved"


class RuntimeReleaseAuthorizationRegistry:
    """Load immutable, provider-free launch authorizations from JSON files."""

    def __init__(
        self,
        authorizations: Mapping[str, RuntimeReleaseAuthorization] | None = None,
    ) -> None:
        self._authorizations = dict(authorizations or {})

    @classmethod
    def from_paths(cls, value: str) -> RuntimeReleaseAuthorizationRegistry:
        authorizations: dict[str, RuntimeReleaseAuthorization] = {}
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            agent_id, separator, raw_path = item.partition("=")
            normalized_agent_id = agent_id.strip()
            if (
                not separator
                or not normalized_agent_id
                or not raw_path.strip()
            ):
                raise ValueError(
                    "AGENT_RUNTIME_RELEASE_AUTHORIZATIONS entries must be "
                    "AGENT_ID=PATH"
                )
            if normalized_agent_id in authorizations:
                raise ValueError(
                    "duplicate Runtime release authorization for "
                    f"{normalized_agent_id}"
                )
            path = Path(raw_path.strip())
            payload = json.loads(path.read_text(encoding="utf-8"))
            authorization = cls._validate_payload(payload, path)
            if authorization.agent_id != normalized_agent_id:
                raise ValueError(
                    "Runtime release authorization Agent mismatch for "
                    f"{normalized_agent_id}"
                )
            authorizations[normalized_agent_id] = authorization
        return cls(authorizations)

    def reason(
        self,
        agent_id: str,
        *,
        suite_id: str,
        launch_mode: str,
        expected_agent_version: str,
        expected_runtime_plan_version: str,
    ) -> str | None:
        authorization = self._authorizations.get(agent_id)
        if authorization is None:
            return "release_authorization_missing"
        if authorization.status != "approved":
            return "release_authorization_revoked"
        if authorization.agent_version != expected_agent_version:
            return "release_authorization_agent_version_mismatch"
        if authorization.runtime_plan_version != expected_runtime_plan_version:
            return "release_authorization_runtime_plan_version_mismatch"
        if authorization.suite_id != suite_id:
            return "release_authorization_suite_id_mismatch"
        if authorization.launch_mode != launch_mode:
            return "release_authorization_launch_mode_mismatch"
        return None

    @staticmethod
    def _validate_payload(
        payload: object, path: Path
    ) -> RuntimeReleaseAuthorization:
        if not isinstance(payload, dict):
            raise ValueError(
                "Runtime release authorization must be a JSON object: "
                f"{path}"
            )
        return RuntimeReleaseAuthorization.model_validate(payload)


__all__ = [
    "RELEASE_AUTHORIZATION_SCHEMA_VERSION",
    "RuntimeReleaseAuthorization",
    "RuntimeReleaseAuthorizationRegistry",
]
