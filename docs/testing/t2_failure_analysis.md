# T2：Failure Attribution 与 Top Failure Patterns

## Scope and evidence

T2 analyzes the T1 machine report without changing implementation, Prompt, expected answers, scorer, or cases. The source is `evaluation/reports/phase_h/latest.json` and its summary. Because 38 rows were loaded from the matching provider-free cache, each pattern is marked as reproducible from the persisted report; a fresh uncached replay is still required before promoting a code fix.

T1 produced 22 non-pass results: 16 failed, 2 errors, and 4 timeouts. There are 17 unique aggregated patterns, so the report contains all patterns rather than inventing empty P18–P20 rows.

## Failure-stage distribution

| Stage | Count | Interpretation |
| --- | ---: | --- |
| `tool_execution` | 4 | three medium and one easy DE cases expose disabled-tool boundaries |
| `timeout` | 4 | teaching/assessment workflows do not reach terminal state within case budgets |
| `routing` | 4 | learning, research, governance, and Phase 3 contract cases miss expected route/agent |
| `generation` | 3 | numeric or keyword mismatches in deterministic academic answers |
| `citation_validation` | 2 | mixed visual cases lack required visual/evidence sections |
| `verification` | 2 | teaching-foundation assertions disagree with actual packet state |
| `course_pack_resolution` | 1 | explicit course-conflict boundary case routes to the wrong pack |
| `unknown / execution_error` | 2 | task creation returns HTTP 409 Conflict for data/research cases |

## Top patterns

`failure_rate` is calculated against 84 executed cases. `Reproducible` means the same failure is represented in the persisted T1 report; it does not claim a fresh no-cache rerun.

| ID | Cases | Failure rate | Severity | Owner | Reproducible | Evidence / representative cases | Likely root cause | Recommended action |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| P01 | 3 | 0.035714 | major | tool policy + DE negative fixtures | yes, cached | `DE_BOOLEAN_001`, `DE_STATE_001`, `DE_VERILOG_001`; `tool_execution/tool_disabled` | cases deliberately request/forbid disabled tools; not random quality loss | T3 tool-selection suite must separate intentional boundary from accidental tool miss |
| P02 | 2 | 0.023810 | critical | teaching runtime / task executor | yes, cached | `COMMERCIAL_ASSESS_001`, `CONTEST_ASSESS_001`; 180 s timeout | assignment-review task does not reach terminal state in offline evaluation | T3 timeout/recovery suite; T4 only after trace-level reproduction |
| P03 | 2 | 0.023810 | critical | teaching runtime / task executor | yes | `COMMERCIAL_FACULTY_001`, `CONTEST_TEACH_001`; 180/240 s timeout | lesson-prep path remains non-terminal under current offline path | T3 teaching timeout suite; preserve timeout budget and inspect checkpoint/worker trace |
| P04 | 2 | 0.023810 | major | evaluation runner / task creation | yes | `COMMERCIAL_DATA_001`, `CONTEST_RESEARCH_001`; HTTP 409 Conflict | duplicate or conflicting task creation state under the shared evaluation identity is not yet attributed | T3 duplicate-task/idempotency fixture; no retry masking before attribution |
| P05 | 1 | 0.011905 | major | evaluation fixture + visual acceptance | yes | `COMMERCIAL_ACADEMIC_VISUAL_001`; mixed input, visual fields missing | case declares mixed visual work but has no attachment in the frozen manifest (`attachment_count=0`) | T3 positive/negative visual fixture with authorized image; do not change expected rubric |
| P06 | 1 | 0.011905 | major | evaluation fixture + visual acceptance | yes | `COMMERCIAL_ACADEMIC_SPECTRUM_001`; same missing visual evidence | same fixture completeness problem as P05, not enough data for image-quality inference | T3 spectrum-image fixture and missing-image refusal case |
| P07 | 1 | 0.011905 | critical | course-pack resolution / routing | yes | `BOUNDARY_COURSE_CONFLICT_001`; `course_mismatch` | conflicting course signal resolves to the wrong course pack | T3 boundary route suite; T4 only if repeated outside the boundary fixture |
| P08 | 1 | 0.011905 | major | academic solver generation | yes | `DE_NUMBER_001`; keyword and numeric mismatch | deterministic answer packet does not satisfy number-encoding rubric | T3 numeric representation cases; compare answer contract before implementation change |
| P09 | 1 | 0.011905 | major | academic solver generation | yes | `AE_OPAMP_001`; numeric mismatch | local graph answer does not preserve expected op-amp numeric value | T3 analog numeric cases; verify reference value and units |
| P10 | 1 | 0.011905 | major | academic solver generation | yes | `CT_POWER_001`; numeric mismatch | local graph answer does not preserve expected power value | T3 circuit numeric cases; check equations/units and tool boundary |
| P11 | 1 | 0.011905 | critical | overall routing / Agent contract | yes | `TP3-05`; route, agent, structure, and status mismatch | a learning-record request is interpreted as academic solving | T3 learning-intent route suite |
| P12 | 1 | 0.011905 | critical | overall routing / learning runtime | yes | `COMMERCIAL_LEARNING_001`; nine contract errors | learning-path scenario falls through to a non-learning route and lacks retest/evidence fields | T3 learning-path positive/negative/boundary suite |
| P13 | 1 | 0.011905 | critical | overall routing / research runtime | yes | `COMMERCIAL_FRONTIER_001`; route/path/status and evidence errors | research frontier request is not routed to the expected research capability | T3 research intent and citation suite |
| P14 | 1 | 0.011905 | critical | overall routing / governance runtime | yes | `COMMERCIAL_GOVERNANCE_001`; route/path/step errors | knowledge-governance intent is not mapped to the commercial workflow contract; model unavailable warning is secondary evidence | T3 governance route suite; do not enable an unconfigured provider |
| P15 | 1 | 0.011905 | major | tool-selection policy | yes | `DE_TRUTH_TABLE_001`; `tool_execution/tool_disabled` | an easy logic case shares the disabled-tool boundary but has a different difficulty | T3 positive tool-enabled vs negative tool-disabled matrix |
| P16 | 1 | 0.011905 | major | Skill mapping / verification | yes | `TF05_AE_SKILL_MAPPING`; `teaching_foundation_mismatch` | expected `AE.Q_POINT` mapping is not reflected in the actual teaching-foundation packet | T3 skill binding and verification contract suite |
| P17 | 1 | 0.011905 | major | learning isolation / verification | yes | `TP3-07`; `teaching_foundation_mismatch` | cross-user isolation assertion is not present in the final packet for this case | T3 cross-user privacy/verification suite |

## Priority selection

The first T3 five are P02, P03, P01, P04, and P05/P06 as one visual-fixture family. Selection uses frequency, severity, user impact, and fixability:

1. Teaching and assessment timeouts affect terminal-state safety and consume the largest latency budget.
2. Tool-disabled DE cases are frequent but partly intentional; the targeted suite must avoid “improving” a negative case by enabling forbidden tools.
3. HTTP 409 task creation can indicate duplicate side effects or an evaluation harness collision and therefore requires trace evidence.
4. Mixed visual cases need real authorized attachments before product quality can be judged.

## Attribution boundaries

- No failure is silently relabeled as a model-quality result when the fixture is incomplete, the provider is unavailable, or a task-creation conflict prevents execution.
- No expected answer or rubric was changed to improve the score.
- The current report is synthetic/provider-free; no real-provider accuracy or cost conclusion is allowed.
- T4 is the first stage permitted to implement a minimal change. Until then, the output is diagnosis and targeted-test design only.
