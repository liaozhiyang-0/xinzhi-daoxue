from __future__ import annotations

from run_full_evaluation import (
    DEFAULT_MANUAL_JUDGEMENTS,
    answer_sha256,
    judgement_passed,
    load_manual_judgements,
    parse_simple_judge,
)


def main() -> int:
    parsed = parse_simple_judge("VERDICT=correct\nSCORE=0.95\nREASON=关键数值一致")
    assert parsed == {
        "verdict": "correct",
        "score": 0.95,
        "reason": "关键数值一致",
    }
    percent_score = parse_simple_judge("VERDICT=incorrect\nSCORE=80\nREASON=结果不一致")
    assert percent_score is not None
    assert percent_score["score"] == 0.8
    assert parse_simple_judge('{"verdict":"correct"}') is None
    assert judgement_passed("correct", 0.95, pass_threshold=0.8)
    assert judgement_passed("partial", 0.85, pass_threshold=0.8)
    assert not judgement_passed("partial", 0.67, pass_threshold=0.8)
    assert not judgement_passed("incorrect", 0.9, pass_threshold=0.8)

    reviews = load_manual_judgements(DEFAULT_MANUAL_JUDGEMENTS)
    assert len(reviews) == 1
    assert len({str(item["case_id"]) for item in reviews}) == 1
    assert all(
        len(str(item["answer_sha256"])) == len(answer_sha256("")) for item in reviews
    )
    print("judgement strategy validation passed: protocol + 1 hash-bound review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
