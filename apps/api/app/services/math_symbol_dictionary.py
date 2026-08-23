from __future__ import annotations

GREEK_SYMBOLS: dict[str, str] = {
    "alpha": r"\alpha",
    "beta": r"\beta",
    "gamma": r"\gamma",
    "delta": r"\delta",
    "theta": r"\theta",
    "lambda": r"\lambda",
    "Lambda": r"\Lambda",
    "mu": r"\mu",
    "omega": r"\omega",
    "phi": r"\phi",
    "pi": r"\pi",
    "tau": r"\tau",
}

OPERATOR_SYMBOLS: dict[str, str] = {
    "infinity": r"\infty",
    "approx": r"\approx",
    "proportional": r"\propto",
    "therefore": r"\therefore",
    "because": r"\because",
}

CIRCUIT_SYMBOLS: dict[str, str] = {
    "iL": "i_L",
    "iC": "i_C",
    "vC": "v_C",
    "vL": "v_L",
    "R1": "R_1",
    "R2": "R_2",
    "omega0": r"\omega_0",
    "omegad": r"\omega_d",
}

SIGNAL_SYMBOLS: dict[str, str] = {
    "omega_s": r"\omega_s",
    "omega_c": r"\omega_c",
    "H_z": "H(z)",
    "X_z": "X(z)",
}

SYMBOLS: dict[str, str] = {
    **GREEK_SYMBOLS,
    **OPERATOR_SYMBOLS,
    **CIRCUIT_SYMBOLS,
    **SIGNAL_SYMBOLS,
}

DEFAULT_PHASOR_STYLE = "underline"
PHASOR_STYLES: dict[str, str] = {
    "underline": r"\underline{{{symbol}}}",
    "dot": r"\dot{{{symbol}}}",
}

DANGEROUS_COMMANDS: frozenset[str] = frozenset(
    {
        "input",
        "include",
        "write",
        "openout",
        "read",
        "usepackage",
        "documentclass",
        "newcommand",
        "def",
        "href",
    }
)

ALLOWED_ENVIRONMENTS: frozenset[str] = frozenset(
    {
        "aligned",
        "alignedat",
        "cases",
        "matrix",
        "pmatrix",
        "bmatrix",
        "vmatrix",
        "Vmatrix",
        "smallmatrix",
    }
)

ALLOWED_COMMANDS: frozenset[str] = frozenset(
    {
        *GREEK_SYMBOLS.values(),
        *OPERATOR_SYMBOLS.values(),
        r"\frac",
        r"\dfrac",
        r"\tfrac",
        r"\sqrt",
        r"\partial",
        r"\int",
        r"\iint",
        r"\iiint",
        r"\oint",
        r"\sum",
        r"\prod",
        r"\lim",
        r"\to",
        r"\infty",
        r"\begin",
        r"\end",
        r"\mathbf",
        r"\mathrm",
        r"\mathcal",
        r"\operatorname",
        r"\text",
        r"\dot",
        r"\ddot",
        r"\underline",
        r"\overline",
        r"\vec",
        r"\hat",
        r"\angle",
        r"\circ",
        r"\cdot",
        r"\times",
        r"\ast",
        r"\pm",
        r"\mp",
        r"\le",
        r"\leq",
        r"\ge",
        r"\geq",
        r"\ne",
        r"\neq",
        r"\in",
        r"\approx",
        r"\propto",
        r"\therefore",
        r"\because",
        r"\sim",
        r"\Rightarrow",
        r"\implies",
        r"\cap",
        r"\cup",
        r"\left",
        r"\right",
        r"\quad",
        r"\qquad",
        r"\sin",
        r"\cos",
        r"\tan",
        r"\log",
        r"\ln",
        r"\exp",
        r"\det",
        r"\min",
        r"\max",
        r"\Pr",
        r"\mathbb",
        r"\nabla",
        r"\Delta",
        r"\Omega",
        r"\sigma",
        r"\rho",
        r"\epsilon",
        r"\varepsilon",
        r"\,",
        r"\;",
        r"\!",
    }
)
