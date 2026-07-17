from app.services.knowledge_base import normalize_query, tokenize


def test_query_normalization_preserves_formula_and_abbreviation() -> None:
    normalized = normalize_query("  ＲＬＣ   PhAsOr  FF  ")

    assert normalized == "rlc phasor ff"
    assert {"rlc", "phasor", "ff"} <= set(tokenize(normalized))
