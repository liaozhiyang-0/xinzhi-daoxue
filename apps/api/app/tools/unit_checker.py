from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UnitCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compatible: bool
    left_dimension: str
    right_dimension: str
    warning: str = ""


_DIMENSIONS = {
    "V": "voltage",
    "mV": "voltage",
    "kV": "voltage",
    "A": "current",
    "mA": "current",
    "uA": "current",
    "Ω": "resistance",
    "ohm": "resistance",
    "kΩ": "resistance",
    "F": "capacitance",
    "uF": "capacitance",
    "H": "inductance",
    "Hz": "frequency",
    "s": "time",
    "W": "power",
}


def check_unit_compatibility(left: str, right: str) -> UnitCheckResult:
    left_dimension = _DIMENSIONS.get(left, "unknown")
    right_dimension = _DIMENSIONS.get(right, "unknown")
    compatible = left_dimension != "unknown" and left_dimension == right_dimension
    warning = "" if compatible else "单位维度不一致或存在未知单位"
    return UnitCheckResult(
        compatible=compatible,
        left_dimension=left_dimension,
        right_dimension=right_dimension,
        warning=warning,
    )
