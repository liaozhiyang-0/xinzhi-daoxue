from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.agents.internal.contracts import VisionExtraction

_STOP_TOKENS = frozenset({"and", "or", "to", "of", "the"})
_SPECIAL_MARKERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "amplitude_or_scale": (("amplitude",), ("scale",)),
    "source_polarity_or_value": (
        ("source", "polarity"),
        ("source", "value"),
    ),
    "bias_values_or_region_boundary": (
        ("bias", "value"),
        ("region", "boundary"),
    ),
    "input_direction_or_time_order": (
        ("input", "direction"),
        ("time", "order"),
    ),
}


def evaluate_visual_acceptance(
    extraction: VisionExtraction,
    specification: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate an optional scenario-level visual capture contract.

    The contract is deliberately additive to generic topology validation. It
    never infers a missing fact; it only checks whether the structured vision
    output contains the fields/tokens explicitly required by the scenario.
    """

    if not isinstance(specification, Mapping):
        return {
            "status": "not_configured",
            "contract_version": "visual_acceptance.v1",
            "missing_must_capture": [],
            "missing_refuse_if_missing": [],
        }

    must_capture = _strings(specification.get("must_capture"))
    refuse_if_missing = _strings(specification.get("refuse_if_missing"))
    searchable = _searchable_features(extraction)
    missing_must_capture = [
        marker for marker in must_capture if not _marker_matches(marker, searchable)
    ]
    missing_refusal = [
        marker
        for marker in refuse_if_missing
        if not _marker_matches(marker, searchable)
    ]
    return {
        "status": (
            "passed"
            if not missing_must_capture and not missing_refusal
            else "blocked"
        ),
        "contract_version": "visual_acceptance.v1",
        "must_capture": must_capture,
        "refuse_if_missing": refuse_if_missing,
        "missing_must_capture": missing_must_capture,
        "missing_refuse_if_missing": missing_refusal,
    }


def _strings(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _searchable_features(extraction: VisionExtraction) -> str:
    parts: list[str] = [
        *extraction.recognized_text,
        extraction.diagram_description,
    ]
    for component in extraction.components:
        parts.extend(
            [
                component.component_type,
                component.label or "",
                component.value or "",
                *component.connections,
                *component.terminal_map.keys(),
                *component.terminal_map.values(),
                component.polarity or "",
                component.reference_direction or "",
            ]
        )
        if component.connections:
            parts.extend(["connections", "topology", "network_topology"])
        if component.terminal_map:
            parts.extend(["terminal_map", "endpoint_mapping"])
        if component.polarity:
            parts.append("polarity")
        if component.reference_direction:
            parts.append("reference_direction")
    raw = " ".join(parts)
    # Real vision providers often return a faithful prose description instead
    # of the compact ``x(t) support [0,1]`` markers used by the contract. Add
    # only facts that are explicitly stated as a signal label plus amplitude
    # and start/end bounds; this is normalization, not visual inference.
    parts.extend(_explicit_signal_features(raw))
    parts.extend(_explicit_spectrum_features(raw))
    parts.extend(_explicit_band_features(raw))
    return _normalize(" ".join(parts))


def _explicit_signal_features(value: str) -> list[str]:
    """Expose explicit prose signal facts as deterministic contract markers."""

    features: list[str] = []
    signal_matches = list(
        re.finditer(r"\b([xh])\s*\(\s*t\s*\)", value, flags=re.IGNORECASE)
    )
    for index, match in enumerate(signal_matches):
        label = match.group(1).casefold()
        end = (
            signal_matches[index + 1].start()
            if index + 1 < len(signal_matches)
            else len(value)
        )
        segment = value[match.start() : end]
        amplitude = re.search(
            r"(?:amplitude|scale|幅值|幅度)\s*(?:is|为|=|:)?\s*"
            r"([-+]?\d+(?:\.\d+)?)",
            segment,
            flags=re.IGNORECASE,
        )
        interval = re.search(
            r"(?:starting\s+at|start(?:ing)?\s+from|from)\s*"
            r"(?:t\s*=\s*)?([-+]?\d+(?:\.\d+)?)"
            r".*?(?:ending\s+at|end(?:ing)?\s+at|to)\s*"
            r"(?:t\s*=\s*)?([-+]?\d+(?:\.\d+)?)",
            segment,
            flags=re.IGNORECASE,
        )
        if interval is None:
            interval = re.search(
                r"([-+]?\d+(?:\.\d+)?)\s*[≤<]\s*t\s*[≤<]\s*"
                r"([-+]?\d+(?:\.\d+)?)",
                segment,
                flags=re.IGNORECASE,
            )
        if interval is None:
            continue
        start, end_value = interval.groups()
        features.extend(
            [
                f"{label} support {start} {end_value}",
                "support interval",
            ]
        )
        if amplitude is not None:
            features.append(f"amplitude {amplitude.group(1)}")
    return features


def _explicit_spectrum_features(value: str) -> list[str]:
    """Expose explicit frequency-axis and finite-support prose markers."""

    normalized = value.casefold()
    features: list[str] = []
    has_frequency_axis = (
        "frequency axis" in normalized
        or "角频率" in normalized
        or "横轴" in normalized and "频率" in normalized
        or "横轴" in normalized and "ω" in normalized
        or "f(jω)" in normalized
    )
    has_pi_support = bool(
        re.search(r"[-−]?π\s*[,，]\s*\+?π", normalized)
    )
    has_spectrum_context = any(
        marker in normalized for marker in ("spectrum", "频谱", "f(jω)", "三角形")
    )
    if has_frequency_axis:
        features.append("frequency axis")
    if has_pi_support and has_spectrum_context:
        features.append("spectrum support -π π")
    return features


def _explicit_band_features(value: str) -> list[str]:
    """Normalize explicit positive/negative band prose without guessing."""

    features: list[str] = []
    band_pattern = (
        r"(?:positive\s*(?:frequency\s*)?band|正频带)\s*"
        r"(?:is|为|=|:|仅在|在|only\s+in)?\s*\[?\s*"
        r"([-+]?\d+(?:\.\d+)?)\s*[,，–−-]\s*"
        r"([-+]?\d+(?:\.\d+)?)\s*\]?\s*(kHz|MHz|Hz)"
    )
    negative_pattern = (
        r"(?:negative\s*(?:frequency\s*)?band|负频带)\s*"
        r"(?:is|为|=|:|仅在|在|only\s+in)?\s*\[?\s*"
        r"([-+]?\d+(?:\.\d+)?)\s*[,，–−-]\s*"
        r"([-+]?\d+(?:\.\d+)?)\s*\]?\s*(kHz|MHz|Hz)"
    )
    for pattern, label in (
        (band_pattern, "positive_band"),
        (negative_pattern, "negative_band"),
    ):
        match = re.search(pattern, value, flags=re.IGNORECASE)
        if match is None:
            continue
        start, end, unit = match.groups()
        features.append(f"{label} {start} {end} {unit}")
        features.extend(["band_edges", "frequency_units"])
    if re.search(r"\b(?:f\s*\(|ω|frequency|频率).*(?:kHz|MHz|Hz)", value, re.I):
        features.append("frequency_units")
    return features


def _marker_matches(marker: str, searchable: str) -> bool:
    normalized_marker = _normalize(marker)
    marker_key = normalized_marker.replace(" ", "_")
    alternatives = _SPECIAL_MARKERS.get(marker_key)
    if alternatives is None:
        tokens = [
            token
            for token in _tokens(normalized_marker)
            if token not in _STOP_TOKENS
        ]
        return bool(tokens) and all(
            _token_present(token, searchable) for token in tokens
        )
    return any(
        all(_token_present(token, searchable) for token in alternative)
        for alternative in alternatives
    )


def _token_present(token: str, searchable: str) -> bool:
    normalized = _normalize(token)
    if not normalized:
        return True
    return all(part in searchable for part in _tokens(normalized))


def _tokens(value: str) -> list[str]:
    return re.findall(
        r"[a-z]+|\d+(?:\.\d+)?|[\u0370-\u03ff]+|[\u4e00-\u9fff]+",
        value.casefold(),
    )


def _normalize(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"\(\s*[a-z]\s*\)", "", normalized)
    normalized = normalized.replace("r-2r", "r2r").replace("r 2 r", "r2r")
    normalized = normalized.replace("r_l", "rl")
    normalized = re.sub(r"[^a-z0-9\u0370-\u03ff\u4e00-\u9fff.]+", " ", normalized)
    return " ".join(normalized.split())
