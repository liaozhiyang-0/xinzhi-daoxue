# Release A5 `/workspace` browser release matrix

Date: 2026-08-26
Surface: `http://127.0.0.1:8000/workspace`
Status: **PARTIAL — not a Release A gate pass**

## Environment

- Browser: Codex in-app Browser, persistent tab, Edge-backed session.
- Product route: legacy workspace HTML/JS surface; `body.workspace-page` was
  present and no `.react-workspace` root was active after a cache-busted reload.
- Service: local API at `127.0.0.1:8000`; persistent DB/Redis/MinIO were not
  cleared.
- Execution identity observed during the current run: `runtime-v3`,
  `canonical-v1`, startup fingerprint
  `4cf777dbb274a7f10a2cbcdd24aef9e3e9635d4d8b628016b121e5b29973dc1b`.

## Browser cases actually executed

| Case | Result | Evidence |
|---|---|---|
| New session + real question | PASS | A new session was created in `/workspace`; task reached terminal completion and answer was visible. |
| Historical session reopen | PASS | Existing session was selected from the sidebar and its answer/history was restored. |
| Answer formula rendering | PASS after fix | `#answer-text .math-expression` labels are `v_P \\approx v_N` and `i_P \\approx 0, i_N \\approx 0`; the previous labels had lost the operators. |
| Material evidence panel | PASS after fix | `资料依据` opened with two evidence cards; both cards contained rendered KaTeX expressions, including `v_P-v_N\\approx0` and `i_P\\approx0`. |
| Direct course evidence linkage | PASS | The answer displayed `S1/S2` references and the evidence panel showed the cited local course documents. |
| Example circuit image + Solver | PASS with review flag | After a cache-busted reload, a fresh session had no inherited draft materials; the real browser example entry attached exactly one `模电测试集_图2.1.1_运算放大器电路.jpg` (17 KB), completed a Solver answer, displayed 5 method-reference cards, and had 0 answer/evidence `math-render-error` nodes after the v8 renderer and session-draft fixes. |
| Real multi-image file chooser | PASS for upload/terminal path | The in-app browser selected two local PNGs through the real file chooser, displayed both previews, submitted a task, and received a terminal answer with 0 answer/evidence `math-render-error` nodes. Semantic image quality remains a separate quality-gate item. |
| Full required matrix | NOT RUN | The 10/10 ordinary, 10/10 Solver, 8 single-image, 5 multi-image, 5 multi-turn, and 5 restart-recovery quotas remain outstanding. |

## Shared defect found and fixed

The persisted task payload contained complete formulas such as
`$v_P \\approx v_N$`. The frontend preprocessor
`normalizeLooseInlineLatex()` only fenced `\\(...\\)`, `\\[...\\]`, and
`$$...$$`; it treated a complete single-dollar formula as loose text and
removed commands such as `\\approx` and `\\frac` before the math scanner ran.

The smallest shared fixes were to treat a complete `$...$` span as protected,
repair only a trailing positive brace balance in truncated evidence formulas,
and route already-delimited inline formulas/list items through the inline
scanner instead of the standalone-math path. The workspace cache-buster was
advanced so an already-open browser cannot keep the old renderer. No Planner,
Runtime, Solver, RAG, task, or storage code was changed for these presentation
fixes.

The first browser matrix also found the concrete failures that motivated the
renderer changes: a retrieved `{v}_{\\mathrm{P}` fragment had one missing
closing brace, and lines such as `$v_I > 0 \\rightarrow v_O$` were
misclassified as standalone formulas. A subsequent follow-up exposed two
more malformed retrieved formulas (`\\va` and mismatched `\\left/\\right`
delimiters). The shared renderer now repairs balanced trailing groups,
normalizes common delimiter-command fragments, and reconciles paired
delimiters before KaTeX. After these fixes, the circuit and historical
evidence cases rendered with zero math errors in both answer and evidence
panels.

The browser run also found that the existing test helper created a new
session after attaching a file, which invalidated the material-attachment
assertion. The real page action was replayed in the correct order.
`resetConversation()` now clears unsent draft materials when switching or
creating a session, preventing stale or duplicate attachments.

## Verification

Passed:

```text
Pytest: `32 passed, 2 warnings` for `apps/api/tests/test_unified_web_ui.py`
Ruff: changed release/test Python files
Node syntax: `apps/api/app/static/debug/ui-core.js` and `workspace.js`
Browser: formula DOM + evidence-card DOM inspection after reload
```

The full targeted UI test and Node syntax checks passed after the v8 renderer
and session-draft fixes; the browser evidence above is from the same v8
candidate.

## Remaining A5 blockers

1. Complete the quota matrix with real `/workspace` submissions.
2. Capture SSE sequence, console errors, network failures, image retention and
   latency per case.
3. Complete the quota matrix with more real single-image and multi-image
   submissions; one real two-image file-chooser submission is now recorded,
   but the original user image is not present as a local workspace file for a
   reproducible replay.
4. Re-run the browser formula case after any Release B Circuit asset changes.
