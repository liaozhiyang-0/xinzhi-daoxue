"""Per-agent launch policy for the incremental Runtime migration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.contracts import AgentRequest
from app.runtime import RuntimeLaunchSnapshot
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorizationRegistry,
)


class RuntimeLaunchMode(StrEnum):
    """Compatibility mode for one Runtime-capable Agent."""

    LEGACY = "legacy"
    SHADOW = "shadow"
    CANARY = "canary"
    DEFAULT = "default"


@dataclass(frozen=True, slots=True)
class RuntimeLaunchDecision:
    agent_id: str
    mode: RuntimeLaunchMode
    source: str
    reason: str
    explicit_opt_in: bool = False

    @property
    def should_execute(self) -> bool:
        return self.mode in {
            RuntimeLaunchMode.CANARY,
            RuntimeLaunchMode.DEFAULT,
        }

    @property
    def requires_runtime(self) -> bool:
        return self.mode == RuntimeLaunchMode.DEFAULT

    def to_snapshot(self) -> RuntimeLaunchSnapshot:
        return RuntimeLaunchSnapshot(
            agent_id=self.agent_id,
            mode=self.mode.value,
            source=self.source,
            reason=self.reason,
            explicit_opt_in=self.explicit_opt_in,
        )

    @classmethod
    def from_snapshot(
        cls, snapshot: RuntimeLaunchSnapshot
    ) -> RuntimeLaunchDecision:
        return cls(
            agent_id=snapshot.agent_id,
            mode=RuntimeLaunchMode(snapshot.mode),
            source=snapshot.source,
            reason=snapshot.reason,
            explicit_opt_in=snapshot.explicit_opt_in,
        )


class RuntimeLaunchPolicy:
    """Resolve Runtime launch intent without invoking a Provider or service."""

    def __init__(
        self,
        launch_modes: str = "",
        *,
        release_registry: RuntimeCanaryReleaseRegistry | None = None,
        release_authorization_registry: (
            RuntimeReleaseAuthorizationRegistry | None
        ) = None,
        release_gate_required: bool = False,
        local_agents: Iterable[str] = (),
    ) -> None:
        self._modes = self._parse_modes(launch_modes)
        self._release_registry = release_registry
        self._release_authorization_registry = release_authorization_registry
        self._release_gate_required = release_gate_required
        self._local_agents = frozenset(local_agents)

    def resolve(
        self,
        agent_id: str,
        request: AgentRequest,
        *,
        lifecycle_enabled: bool,
        runtime_option_key: str | None = None,
        expected_agent_version: str | None = None,
        expected_runtime_plan_version: str | None = None,
        execution_allowed: bool = True,
        execution_block_reason: str = "agent_execution_unavailable",
    ) -> RuntimeLaunchDecision:
        if not execution_allowed:
            return RuntimeLaunchDecision(
                agent_id=agent_id,
                mode=RuntimeLaunchMode.LEGACY,
                source="agent_availability",
                reason=execution_block_reason,
            )
        explicit = self._explicit_runtime_option(request, runtime_option_key)
        configured = self._modes.get(agent_id)
        is_local_runtime = agent_id in self._local_agents
        if explicit is False:
            return RuntimeLaunchDecision(
                agent_id=agent_id,
                mode=RuntimeLaunchMode.LEGACY,
                source="explicit_opt_out",
                reason="request_disabled_runtime",
            )
        if configured is not None:
            if explicit is True and configured in {
                RuntimeLaunchMode.LEGACY,
                RuntimeLaunchMode.SHADOW,
            }:
                mode = (
                    RuntimeLaunchMode.CANARY
                    if lifecycle_enabled
                    else RuntimeLaunchMode.LEGACY
                )
                release_reason = (
                    self._release_gate_reason(
                        agent_id,
                        target_mode=mode,
                        expected_agent_version=expected_agent_version,
                        expected_runtime_plan_version=expected_runtime_plan_version,
                    )
                    if mode == RuntimeLaunchMode.CANARY
                    else None
                )
                if release_reason is not None:
                    return RuntimeLaunchDecision(
                        agent_id=agent_id,
                        mode=RuntimeLaunchMode.LEGACY,
                        source="canary_release_gate",
                        reason=release_reason,
                    )
                return RuntimeLaunchDecision(
                    agent_id=agent_id,
                    mode=mode,
                    source="explicit_opt_in",
                    reason=(
                        "explicit_runtime_option"
                        if lifecycle_enabled
                        else "runtime_lifecycle_disabled"
                    ),
                    explicit_opt_in=True,
                )
            if not lifecycle_enabled and configured in {
                RuntimeLaunchMode.CANARY,
                RuntimeLaunchMode.DEFAULT,
            }:
                return RuntimeLaunchDecision(
                    agent_id=agent_id,
                    mode=configured,
                    source="configured_launch_mode",
                    reason="runtime_lifecycle_disabled",
                )
            release_reason = (
                None
                if is_local_runtime
                else self._release_gate_reason(
                    agent_id,
                    target_mode=configured,
                    expected_agent_version=expected_agent_version,
                    expected_runtime_plan_version=expected_runtime_plan_version,
                )
            )
            if (
                release_reason is not None
                and configured in {RuntimeLaunchMode.CANARY, RuntimeLaunchMode.DEFAULT}
            ):
                return RuntimeLaunchDecision(
                    agent_id=agent_id,
                    mode=RuntimeLaunchMode.LEGACY,
                    source="canary_release_gate",
                    reason=release_reason,
                )
            return RuntimeLaunchDecision(
                agent_id=agent_id,
                mode=configured,
                source="configured_launch_mode",
                reason="configured_agent_launch_mode",
                explicit_opt_in=explicit is True,
            )
        if explicit is True:
            # Local business Runtimes are already governed by the local
            # implementation registry and human review boundary.  An
            # explicit ``*_runtime.execute=true`` request must not send them
            # through the cloud canary release gate; doing so turns a valid
            # local task into a misleading ``registered Runtime disabled``
            # failure whenever the deployment keeps the cloud gate enabled.
            if is_local_runtime:
                return RuntimeLaunchDecision(
                    agent_id=agent_id,
                    mode=(
                        RuntimeLaunchMode.DEFAULT
                        if lifecycle_enabled
                        else RuntimeLaunchMode.LEGACY
                    ),
                    source="explicit_opt_in",
                    reason=(
                        "explicit_runtime_option"
                        if lifecycle_enabled
                        else "runtime_lifecycle_disabled"
                    ),
                    explicit_opt_in=True,
                )
            release_reason = (
                self._release_gate_reason(
                    agent_id,
                    target_mode=RuntimeLaunchMode.CANARY,
                    expected_agent_version=expected_agent_version,
                    expected_runtime_plan_version=expected_runtime_plan_version,
                )
                if lifecycle_enabled
                else None
            )
            if release_reason is not None:
                return RuntimeLaunchDecision(
                    agent_id=agent_id,
                    mode=RuntimeLaunchMode.LEGACY,
                    source="canary_release_gate",
                    reason=release_reason,
                )
            return RuntimeLaunchDecision(
                agent_id=agent_id,
                mode=(
                    RuntimeLaunchMode.CANARY
                    if lifecycle_enabled
                    else RuntimeLaunchMode.LEGACY
                ),
                source="explicit_opt_in",
                reason=(
                    "explicit_runtime_option"
                    if lifecycle_enabled
                    else "runtime_lifecycle_disabled"
                ),
                explicit_opt_in=True,
            )
        # A business Runtime may advertise itself as an automatic candidate
        # when the registry resolves the request without a runtime option
        # (for example, the general-question Runtime).  Preserve the
        # migration safety boundary by requiring the lifecycle flag, while
        # allowing that registered candidate to enter the canary path without
        # making callers add an internal implementation option manually.
        if is_local_runtime and lifecycle_enabled and runtime_option_key is not None:
            return RuntimeLaunchDecision(
                agent_id=agent_id,
                mode=RuntimeLaunchMode.DEFAULT,
                source="local_runtime_registry",
                reason="registered_local_runtime",
            )
        if lifecycle_enabled and runtime_option_key is not None:
            release_reason = (
                self._release_gate_reason(
                    agent_id,
                    target_mode=RuntimeLaunchMode.CANARY,
                    expected_agent_version=expected_agent_version,
                    expected_runtime_plan_version=expected_runtime_plan_version,
                )
                if self._release_gate_required
                else None
            )
            if release_reason is not None:
                return RuntimeLaunchDecision(
                    agent_id=agent_id,
                    mode=RuntimeLaunchMode.LEGACY,
                    source="canary_release_gate",
                    reason=release_reason,
                )
            return RuntimeLaunchDecision(
                agent_id=agent_id,
                mode=RuntimeLaunchMode.CANARY,
                source="runtime_registry_candidate",
                reason="registered_runtime_auto_candidate",
            )
        return RuntimeLaunchDecision(
            agent_id=agent_id,
            mode=RuntimeLaunchMode.LEGACY,
            source="default_legacy",
            reason="no_runtime_launch_mode",
        )

    def lifecycle_enabled(self, global_shadow_enabled: bool) -> bool:
        return global_shadow_enabled or any(
            mode in {
                RuntimeLaunchMode.SHADOW,
                RuntimeLaunchMode.CANARY,
                RuntimeLaunchMode.DEFAULT,
            }
            for mode in self._modes.values()
        )

    def configured_mode(self, agent_id: str) -> RuntimeLaunchMode | None:
        """Expose the configured mode for diagnostics without allowing mutation."""

        return self._modes.get(agent_id)

    @property
    def release_gate_required(self) -> bool:
        return self._release_gate_required

    def _release_gate_reason(
        self,
        agent_id: str,
        *,
        target_mode: RuntimeLaunchMode,
        expected_agent_version: str | None,
        expected_runtime_plan_version: str | None,
    ) -> str | None:
        if not self._release_gate_required:
            return None
        if not self._version_expectations_available(
            expected_agent_version, expected_runtime_plan_version
        ):
            return "canary_artifact_version_expectation_missing"
        if self._release_registry is None:
            return "canary_release_evidence_missing"
        if self._release_registry.release_eligible(
            agent_id,
            expected_agent_version=expected_agent_version,
            expected_runtime_plan_version=expected_runtime_plan_version,
        ):
            release_reason = None
        else:
            release_reason = self._release_registry.reason(
                agent_id,
                expected_agent_version=expected_agent_version,
                expected_runtime_plan_version=expected_runtime_plan_version,
            )
        if release_reason is not None:
            return release_reason
        if self._release_authorization_registry is None:
            return "release_authorization_missing"
        report = self._release_registry.report(agent_id)
        if report is None:
            return "canary_release_evidence_missing"
        return self._release_authorization_registry.reason(
            agent_id,
            suite_id=report.suite_id,
            launch_mode=target_mode.value,
            expected_agent_version=expected_agent_version or "",
            expected_runtime_plan_version=expected_runtime_plan_version or "",
        )

    @staticmethod
    def _version_expectations_available(
        expected_agent_version: str | None,
        expected_runtime_plan_version: str | None,
    ) -> bool:
        return bool(
            expected_agent_version
            and expected_agent_version.strip()
            and expected_runtime_plan_version
            and expected_runtime_plan_version.strip()
        )

    @staticmethod
    def _explicit_runtime_option(
        request: AgentRequest,
        runtime_option_key: str | None,
    ) -> bool | None:
        """Read launch intent without reinterpreting business ``execute`` flags.

        Runtime-native options use the ``*_runtime`` suffix, where ``execute``
        is a launch opt-in/out. Other registered options, such as
        ``research_analysis_v2``, activate a Runtime-backed business capability
        but keep their own domain-specific meaning for ``execute``.
        """

        if runtime_option_key is not None:
            value = request.options.get(runtime_option_key)
            if not isinstance(value, dict):
                return None
            if not runtime_option_key.endswith("_runtime"):
                return True
            execute = value.get("execute")
            return execute if isinstance(execute, bool) else True

        values: list[bool] = []
        for key, value in request.options.items():
            if not key.endswith("_runtime") or not isinstance(value, dict):
                continue
            execute = value.get("execute")
            if isinstance(execute, bool):
                values.append(execute)
        if any(value is False for value in values):
            return False
        if any(value is True for value in values):
            return True
        return None

    @staticmethod
    def _parse_modes(value: str) -> dict[str, RuntimeLaunchMode]:
        modes: dict[str, RuntimeLaunchMode] = {}
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            agent_id, separator, raw_mode = item.partition("=")
            if not separator or not agent_id.strip():
                raise ValueError(
                    "AGENT_RUNTIME_LAUNCH_MODES entries must be AGENT_ID=MODE"
                )
            normalized_agent = agent_id.strip()
            if normalized_agent in modes:
                raise ValueError(
                    f"duplicate Runtime launch mode for {normalized_agent}"
                )
            try:
                modes[normalized_agent] = RuntimeLaunchMode(raw_mode.strip())
            except ValueError as exc:
                allowed = ", ".join(mode.value for mode in RuntimeLaunchMode)
                raise ValueError(
                    f"invalid Runtime launch mode for {normalized_agent}; "
                    f"expected one of: {allowed}"
                ) from exc
        return modes
