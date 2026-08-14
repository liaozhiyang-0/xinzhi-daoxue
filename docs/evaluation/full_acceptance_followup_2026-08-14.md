# Full acceptance follow-up — 2026-08-14

This addendum records the final bounded round. It does not replace the earlier acceptance log and does not claim the incomplete Edge matrix passed.

## Date-scope root cause and fix

The researcher workflow had three related defects: relative requests such as “recent five years” were converted to a fixed three-year retrieval window; undated results were accepted; and generated research briefs were not checked for year claims outside the requested range. This allowed a future-dated external result and an inconsistent 2019–2024 narrative to reach the Edge evidence view.

The non-protected research services now parse the requested relative window, prefer publication date over update date, reject missing/future/out-of-window records for date-sensitive queries, and fall back to deterministic evidence text when a generated brief contains out-of-range years. A focused regression test covers undated and old candidates.

## Verification

- `pytest -q apps/api/tests/test_academic_paper_review.py apps/api/tests/test_external_search_and_fetch.py --no-cov`: 26 passed, 2 warnings.
- Ruff on the changed date-scope services/tests: passed.
- Mypy on the changed date-scope services: passed.
- `node --check apps/api/app/static/debug/admin.js` and `workspace.js`: passed.
- `git diff --check`: exit 0; only existing LF/CRLF conversion warnings.
- One launcher/API chain was active during Edge work; its exact parent/child tree was stopped afterward and port 8000 was confirmed released.

## Edge acceptance boundary

The final Edge date-scope retest is not accepted as passed: two small DOM reads timed out in the Edge control layer after submission. The earlier Edge research run remains a pre-fix reproduction and direct DOI-link check, not evidence that the new date-scope behavior rendered correctly.

The full pytest suite was not claimed as passed in this round; prior bounded full/admin runs exceeded their time limits before reliable completion. Remaining release risks are the unresolved Edge DOM timeout, incomplete teacher post-approval DOM verification, and the user-requested incomplete matrix for long-wait, stop/recovery, empty/error, insufficient-data, multi-domain routing, and all administrator modules.

## v27 launcher and evidence follow-up

- The launcher/frontend contract was corrected: `scripts/team_launcher.py` had a stale `FRONTEND_BUILD_ID` (v25) while the served workspace assets were v26. That mismatch could make repair classify a healthy page as stale and repeatedly restart the chain. The contract is now v27 and has a regression test.
- `ui-core.js` now bounds markdown input at 120,000 characters and visibly labels truncation. This is a bounded rendering guard, not a replacement for source evidence.
- Fresh Edge student page: result restored after reload; two local course evidence cards were visible; opening the first source rendered `完整原文 23,572–31,655 / 126,771 字符`, 4,251 visible characters, and the formula parsing caveat. The backend document-page request returned HTTP 200 with 7,816 content characters and matching anchor status. A new session then showed `0 条消息` and no old evidence cards.
- Fresh Edge researcher submission reached backend task `task_65a6f444991d438893c20d6657d61e4b`, completed on `RESEARCH_01_ACADEMIC_SEARCH_V1`, with 27 contiguous events and 3 external retrieval items. The Edge terminal DOM read timed out, so this is backend evidence only and is not an Edge UI pass.
- `doctor --port 8000` passed 12/12 checks after the v27 correction. The single chain required more than 100 seconds to become listenable during restart; deferred RAG warmup logged about 32 seconds. This remains a startup-time risk for the user-facing long-wait experience.

## Runtime governance boundary

- `check_runtime_readiness_projection.py --base-url http://127.0.0.1:8000`: valid, provider-free, 12 task agents, 8 task capabilities, 2 learning capabilities, no errors.
- Release preflight was run for the seven non-protected local/published agents. All seven correctly returned `release_eligible=false` because the release record did not supply expected Agent/Runtime-plan versions and matching structural/semantic evidence sidecars. This is an explicit release-governance gap; no protected research runtime was inspected or changed, and no `RESEARCH_03` promotion was attempted.

## v31 formula-preservation correction

The user-facing requirement is now explicit: a knowledge fragment must not replace an unparsed formula with a generic warning or discard source characters. The observed root cause was malformed/OCR-style LaTeX in retrieved summaries and source fragments (including unbalanced delimiters), not a missing source document.

- `ui-core.js` keeps the raw formula in a bounded `<code class="math-latex-fallback">` when the structure guard rejects unsafe KaTeX input; it no longer emits the generic replacement sentence.
- Evidence cards and the source dialog use `preserveRaw` rendering. Anchor normalization remains separate and is not used to rewrite the visible evidence text. Table, heading, and list branches now pass the same preservation option.
- Edge v29 verification showed two source cards with raw formula text retained. Opening the first local source loaded the original fragment successfully; the visible document had no generic “formula not fully parsed” replacement text. Five raw fallback formula nodes were observed in the loaded document and retained their source strings.
- `doctor --port 8000` passed 12/12 while the one API chain was listening. The launcher regression suite passed 31 tests. Ruff, Mypy, Node syntax checks, and `git diff --check` passed after the final patch.

The two web contract test modules were bounded at 90 seconds and did not finish within the limit; they are not claimed as passed. The complete Edge role/task matrix also remains incomplete, so the project is not reported as fully accepted.

## v32 evidence content-type policy and approval retest

The first evidence-filter patch was incomplete because the formal teacher path used the lexical `TaskRunner` fallback when RAG was disabled; that path returned waveform and mixed-content candidates without applying the configured lesson-preparation content-type policy. The visual-parent vector retrieval path also needed to carry the same policy. The non-protected fixes now apply the policy in the vector store, RAG-disabled sparse fallback, and `TaskRunner` lexical fallback, with focused multimodal regression coverage.

- `pytest -q apps/api/tests/test_multimodal_rag.py --no-cov`: 13 passed, 2 warnings.
- Ruff and Mypy on the changed retrieval/presentation files: passed.
- Runtime readiness projection: valid, provider-free, no errors.
- Formal Edge teacher retest created `task_e6a5966b2bb446bbbb743786615b895c`; the authenticated administrator task center performed submit/confirm approval. The admin detail then showed `completed`, 5 evidence items, 29 events, and contiguous event numbering.
- The teacher guest page correctly entered the approval wait state and the backend task completed, but a fresh page navigation did not restore the guest session's completed task card. This is recorded as an unresolved UI session-recovery defect; no direct API or database bypass was used.
- The debug execution approval control also returned the explicit 403 message that the current identity was not authorized. The admin task-center flow succeeded after authenticating as an administrator, confirming the permission boundary rather than a silent approval failure.

This retest does not claim the full teacher evidence-card visual assertion passed, because the guest session restoration issue prevented the final card DOM read. The project therefore remains not fully accepted.

## v32 follow-up: session-task recovery and formal Edge retest

The previous teacher refresh observation mixed identities: the task was created as a guest, while the refreshed Edge page had an authenticated teacher identity. The backend correctly denied cross-identity task recovery. A same-identity retest was therefore required before treating this as a product defect.

- Root cause addressed in `workspace.js`: recovery depended on the latest assistant message carrying `source_task_id`. A refreshed browser can observe the session task before the assistant message commit is visible. Recovery now reads the session task history, hydrates the newest task through the owned task endpoint, and uses that full task payload for the same result/evidence renderer. The assistant-message path remains as a compatibility fallback.
- `workspace.html`, `team_launcher.py`, and the student page contract were advanced to build `20260814-evidence-raw-v32`; a focused regression assertion covers session-task recovery.
- Formal Edge student retest: a local concept task completed with 3 evidence cards; after a fresh navigation, the answer, 3 cards, raw formula text, and session remained visible and consistent. The freeze card was disabled and explicitly stated that data analysis was frozen.
- Formal Edge teacher retest with the same authenticated teacher identity: an existing completed lesson-preparation session was selected and then refreshed. The page restored the lesson title, one conversation message, and the completed answer state. A new teacher task was stopped from the UI and showed `已停止` with a clear no-result notice.
- Formal Edge researcher retest: the academic search completed with `带提示完成`, one external evidence item, and a clickable arXiv URL `https://arxiv.org/abs/2501.09140v1` rendered as both the title link and “打开论文” link. The duplicate links point to one evidence identity, not two evidence cards.
- `pytest -q apps/api/tests/test_multimodal_rag.py apps/api/tests/test_task_presentation.py apps/api/tests/test_task_presentation_external_legacy.py apps/api/tests/test_data_analysis_freeze.py --no-cov`: 34 passed, 2 warnings.
- `doctor --port 8000`: 12/12 passed; API, database, Redis, MinIO, and single local executor were healthy. `node --check` passed for workspace, ui-core, and admin scripts. `git diff --check` passed.

The broader Edge matrix is still incomplete: empty/error result workflows, browser disconnect/reconnect, pause/resume, structured-file workflow, multi-domain routing, and all administrator modules have not all been freshly recorded in this bounded round. The two broader Web UI pytest modules also exceeded their bounded timeout and are not claimed as passed. No protected RESEARCH_03 source or test was read, modified, or audited; no SOLVER_CT v1.0 change was made.

## v33 bounded Edge continuation

- Browser return/reconnect simulation: a long academic-search task was submitted, the page was navigated away and returned, and the same session restored the in-progress conversation. It later rendered `带提示完成` with one external evidence item. No duplicate evidence card was observed.
- Long-wait behavior: an assignment-review task remained running for 85 seconds; the page changed to `模型响应较慢，仍会自动完成`, reported that the task stayed in the background, and did not show a false completed or empty-success state. The task was then stopped from Edge and the page showed `已停止` with a no-result notice.
- Pause/resume: ordinary knowledge tasks completed before a usable pause control was exposed. This is not counted as a pass; a dedicated pause-capable Runtime scenario is still required.
- Structured-file workflow: the in-app browser control surface does not expose local file injection, so the repository CSV fixture could not be uploaded through the formal Edge UI. No upload success was fabricated; this remains an environment-blocked Edge case.
- Assignment/teaching routing: the assignment task entered the correct long-wait state and was safely stopped. Its final answer was intentionally not claimed because the bounded run was cancelled.
- Health after the bounded tasks: `/api/v1/health` returned HTTP 200 with `ok` for API, database, Redis, and MinIO; the single launcher/API chain remained active.

## v35 routing, freeze-boundary, and session-cleanup continuation

- Formal Edge multi-domain task: the query combined capacitor continuity with a recent academic-evidence request. The page routed it to `科研前沿检索与证据简报`, rendered one external evidence item, and did not fabricate local course evidence. This matches the router's strong research/cross-domain precedence over a stale course hint.
- Data-analysis freeze boundary: a natural-language request asking for effect-size analysis produced no `data-task-id`, no persisted Task, and no `RESEARCH_03` execution. The page showed `未执行 · 数据边界` and stated that no authorized data would be read or analyzed. The disabled data-analysis capability card remained visible with the freeze explanation.
- Admin Edge module sweep: `overview`, `tasks`, `files`, `agents`, `settings`, and `system` each became visible and loaded content. The task center displayed task totals, active/success/failure counters, task Agent identities, and execution-chain actions. The files center displayed ingestion status, page count, task association, and storage summary.
- Session cleanup: after entering a concept prompt and starting a new session before submission, the new session had zero conversation messages, zero evidence cards, a hidden answer panel, and a hidden research-analysis panel. No prior task state was carried into the new session.
- A failed-task table observation was not accepted: the bounded Admin interaction remained on the Agent list after attempting the failed-status filter, so no new claim is made about the failed-result detail UI.

Remaining acceptance gaps are the formal Edge structured-file upload (local file injection is unavailable in the browser control surface), a dedicated empty/error-result workflow, and reliable final failed-task detail selection in the Admin UI. No protected RESEARCH_03 source or test was read, modified, or audited.

## v36 administrator failure-filter retest

- A fresh formal Edge session logged into a local acceptance administrator account.
- Opening the `tasks` module showed the task summary and task table. Selecting the task status `failed` and submitting the form returned 21 failed tasks; every displayed row carried the failed badge and a `查看详情` action.
- Opening `task_230b9079fd1b43f0bf05b4fe9cc50098` rendered the detail panel with `failed / AE / assignment_review`, `0` evidence items, `13` events, and contiguous event numbering. Expanding the execution chain showed the terminal `task.failed` event with `error_code=runner_shutdown`.
- The earlier report that the interaction remained on the Agent module was not reproduced. Source inspection also confirmed that `loadAdminTasks()` serializes the selected `status` field into the admin task query. No administrator filtering code was changed in this retest.
- This closes the reliable failed-task filter/detail observation. It provides a real failed-result UI record; it is not treated as a successful or empty result.

## v37 insufficient-course-evidence correction

- Formal Edge reproduced a real course-scoped insufficiency case with the course selector set to CT and a question about an unrelated Mars superconducting-grid/quantum-gravity chapter. Before the fix, unrelated CT candidates were exposed as course evidence. The root cause was that retrieval candidates were retained separately from the topic-filtered context packet, and `TaskRunner` projected the unfiltered candidate list into `knowledge.hits`.
- The non-protected fix filters candidate hits by meaningful topic overlap, projects only `retrieval_packet.evidence` into the task result, and adds regression coverage for unrelated topics, valid topic anchors, structural terms, and rejected candidate presentation. Focused retrieval/presentation/runtime tests passed: 35 passed, 2 warnings.
- The first post-fix Edge run showed 0 course materials and no unrelated evidence cards, but the Runtime verification correctly failed closed. Its durable execution chain showed `knowledge.execute` succeeded with `evidence_status=insufficient`, `knowledge.verify` returned `partial` with `reason_code=knowledge_evidence_insufficient`, and the Runtime terminal status became `failed`. The UI nevertheless fell back to a generic old-response presentation because the failure path discarded the structured conservative answer.
- The follow-up fix preserves the non-authoritative Runtime result snapshot on failure and adds an explicit UI presentation. Final formal Edge retest showed `课程依据不足`, `课程资料 0`, the conservative “暂时没有在当前课程知识库中检索到足够依据” answer, an explicit warning that unrelated fragments were blocked, and no evidence cards. The Runtime control remained `执行失败` by design; this is a safe evidence-gated insufficiency result, not a successful answer.
- Current acceptance status for this scenario: no fabricated evidence and user-facing explanation passed; task terminal status remains failed closed and is recorded as a product-risk/degraded-path observation rather than a normal success.

## v34 pause/resume control evidence

- A dedicated Edge academic-search run was polled while active. The Runtime pause control first became visible and enabled while the task was running.
- Clicking pause produced the explicit pending-control message. The Runtime then converged to `已暂停` and exposed an enabled resume control.
- Clicking resume returned the Runtime to `正在执行`; the task then completed with `带提示完成` and two external evidence cards.
- Admin Edge execution-chain review for the same task showed `pause_requested`, `resume_requested`, and `runtime_control` events. The detail summary reported 32 events with contiguous sequence numbers and ended with `task.completed`.
- This is a real Edge pause/resume pass. The earlier “not observed” result came from ordinary tasks completing before their control projection became available.
-
## v38 explicit-query evidence gate follow-up

- Root cause: the lesson-preparation Runtime retrieval path called `RetrievalContextService` with the RAG service's internal query string. That string could lose the user's specific topic, so the presentation still displayed unrelated same-course candidates as `进入上下文`.
- Non-protected fix: `RetrievalContextService.build()` accepts an optional `query_override`; `GeneralQuestionRuntimeService` passes the original user question for topic filtering and packet traceability. Raw source/formula content is unchanged and remains preserved for display.
- Regression verification: the focused retrieval/presentation/runtime/freeze command passed 39 tests with 2 existing warnings. Ruff, Mypy, and `git diff --check` passed for the changed scope.
- The service was safely reloaded through `team_launcher.py start --port 8000 --force-reload`. Final `doctor --port 8000` passed 12/12, `/health` returned HTTP 200, and the listener remained one project-owned API chain with local executor mode.
- Formal Edge follow-up restored the persisted teacher task to `等待人工审批`; its evidence pane showed `本次没有可展示的资料依据` before post-retrieval completion. This run is not counted as a visual pass for the new relevant-only card assertion. The Edge control layer then timed out during the admin detail read; no false pass is claimed.
- Earlier formal Edge evidence remains valid for course raw-formula preservation, external research links, same-identity refresh recovery, pause/resume, long-wait/stop, insufficient-course-evidence fail-closed presentation, multi-domain routing, data-analysis freeze, and administrator coverage. The new explicit-query gate still needs one completed teacher post-approval Edge card read before release acceptance.

## v39 post-approval relevant-evidence card retest

- The remaining evidence-card defect was traced one layer below the Runtime boundary: the legacy compatibility/fallback path in `TaskRunner` and `KnowledgeQAService` rebuilt retrieval context without preserving the user's original question. The topic filter therefore saw an internal generic query. A second guard now treats `lesson_prep` and `assignment_review` as teaching intents and requires the requested topic to appear in source metadata, while leaving raw source content untouched for display.
- Non-protected changes: `retrieval_context.py`, `task_runner.py`, `knowledge_qa_service.py`, `test_retrieval_context_packet.py`, and `test_knowledge_qa_service.py`. The regression suite covers the compatibility path and rejects a teaching candidate whose topic occurs only incidentally in its body.
- Verification: the focused command covering retrieval, compatibility presentation, runtime contracts, and the data-analysis freeze passed `44 passed, 2 warnings`; Ruff and Mypy passed on the changed Python scope.
- Formal Edge same-identity teacher retest: a new CT lesson-preparation task entered `等待人工审批` after the bounded wait, was submitted through the UI, and converged to `已完成`. The answer displayed the requested capacitor-voltage-continuity topic, `已检索 3 条课程资料`, and retained the raw formula/source strings. The three evidence cards were S1–S3 and all carried the source topic `2. 电容电压连续性`; the previously observed unrelated `1.2.4 电路理论的基本假设` and `9.3.2 RLC 并联电路` cards were absent.
- Refresh retest: after a full page reload, the same answer, three topic-matched cards, and raw formula content remained visible. No generic `公式片段未完整解析` replacement appeared. The teacher-side task lifecycle and evidence presentation are therefore accepted for this path.
- The administrator task-center table and detail view were also inspected during the retest; the previously completed approval task showed `completed`, 5 evidence items, 29 events, and continuous sequence numbers. This is retained as the earlier approval-chain record; the new teacher-side post-fix card read is the acceptance evidence for the relevant-only filter.
- Release boundary: the full role/task matrix is not claimed complete. Structured-file upload remains blocked by the in-app Edge control surface's lack of local file injection; the broad Web UI pytest modules previously exceeded their bounded timeout; formal Runtime migration still contains compatibility fallback paths; RESEARCH_03 remains frozen and was not read, modified, or audited.

## v40 evidence provenance and refresh acceptance

- Formal Edge student path: after selecting guest mode, a CT course question about capacitor-voltage continuity completed with `已检索 3 条课程资料`. The three cards were S1–S3, all titled `2. 电容电压连续性`, with course `电路理论`, source chapter/title metadata, and preserved raw formula strings. No unrelated RLC or generic circuit-theory cards appeared.
- The first submission before choosing an entry mode did not create a Task; the UI correctly kept the input visible behind the entry modal. After selecting `以游客模式进入`, the same submission created the Task and the page rendered the real progress chain. This is recorded as a user-flow prerequisite, not an API failure.
- Formal Edge researcher path: a RAG literature request completed with 6 `academic_paper` cards. The result carried title, provider/source type, author/venue metadata, abstract, identifier, and one canonical link per source. Duplicate title/identifier projections were not rendered as duplicate cards.
- The 6 canonical links were inspected in the UI: 4 arXiv URLs and 2 DOI URLs. An arXiv URL opened to the corresponding arXiv abstract page, and a DOI URL opened to the corresponding Springer article page. After a full page reload and after switching away and back to the research session, the answer and all 6 `打开论文` links remained present with the same hrefs.
- Formal Edge CT insufficiency path: a Mars quantum-gravity/superconducting-grid request with CT selected completed as `课程依据不足`, showed `课程资料 0`, displayed the conservative no-evidence message, and rendered zero evidence cards and zero external links. This confirms fail-closed presentation rather than fabricated course support.
- No Mock source was exposed in these real Edge tasks. The external card renderer retains an explicit development-Mock label when provider metadata identifies a Mock result; the local health response remained explicitly `active_provider=mock` only as the configured development provider, not as a real-source claim.
- No new code change was required by this Edge pass; the provenance fixes are the existing `task_presentation.py`, `workspace.js`, `external_research_answer.py`, retrieval-context, and result-commit changes. The Edge evidence closes the previously pending relevant-card and refresh-consistency checks for local and external evidence, while structured-file upload remains unverified because the browser control surface cannot inject a local file.

## v41 uploaded-document routing correction and bounded verification

- The first bounded `test_document_ingestion.py` run exposed a real defect in the upload-to-task path: an extracted `task-note.txt` attachment was classified as `text_and_data_file`, so the text-capable academic solver rejected task creation with HTTP 422 (`agent_input_not_supported`).
- The non-protected correction is limited to input classification. `TaskRouter` and `AgentExecutionPlanner` now recognize only CSV/TSV/JSON/Excel/Parquet MIME types or suffixes as structured data files. Ordinary text/PDF/Word attachments remain text-compatible after hydration; tabular files retain the data-file modes.
- Added a router regression for a ready `text/plain` attachment. Verification passed: `test_task_router.py` plus `test_agent_runtime.py` reported 50 passed; the complete `test_document_ingestion.py` reported 12 passed. Ruff passed on the changed scope, Mypy passed on the two changed source files, `git diff --check` passed, and the sensitive-file scan passed.
- Runtime verification remained healthy after the correction: `team_launcher.py doctor --port 8000` reported 12/12, the readiness projection was valid with no errors, and `/api/v1/health` returned HTTP 200 with database/Redis/MinIO `ok`. The launcher still detected one project-owned API chain and no separate Worker was required in local-executor mode.
- Formal Edge structured-file upload is still not claimed as passed. The upload input is present in the UI, but the in-app Edge control surface timed out while opening the local file chooser. The environment remediation is to enable `Allow access to file URLs` for the ChatGPT/Edge control extension in `edge://extensions`, then repeat the CSV upload flow. Backend upload and document-ingestion tests pass; this does not substitute for the required formal Edge result.
- Protected boundaries remain unchanged: no diff was found for `research_analysis_runtime.py` or `test_research*`, and no SOLVER_CT v1.0, raw Xingchen YAML, student-private data, or `experiment_demo.csv` was added.

## v42 external evidence metadata correction and bounded Edge follow-up

- Formal Edge inspection found a provenance display mismatch in a real completed research task: the canonical Runtime payload contained `updated_at`/`published_at`, but the card metadata rendered only the legacy `date_label` field. The answer body had dates while the cards showed `时间未知`, so the source metadata was not internally consistent.
- Non-protected fix: `workspace.js` now derives a stable `YYYY-MM-DD` card date from `date_label`, then `updated_at`, then `published_at`; `workspace.html`, `team_launcher.py`, and the student web contract were advanced to `20260814-evidence-raw-v42` so the browser cannot reuse the prior asset version. The fix does not alter source identity, abstracts, URLs, or evidence selection.
- Narrow verification passed: the external-evidence deduplication/count/UI contract tests reported 3 passed; Ruff passed for the touched retrieval source; `node --check` passed for `workspace.js` and `ui-core.js`. A broader `test_unified_web_ui.py` + `test_student_web.py` run was bounded at 120 seconds and did not finish; it is not claimed as passed.
- Formal Edge evidence before the fix remains valid for six external cards, unique evidence IDs, arXiv/DOI links, source abstracts, refresh/session recovery, and fail-closed insufficiency. A new v42 Edge post-fix read could not be completed: the browser control layer timed out repeatedly while reopening old tabs and while creating a fresh tab. This is an environment/control limitation, not evidence that the patch passed visually.
- The same bounded Edge run reached `runtime_plan_proposal / approval_required` after external retrieval. Guest-side approval controls were correctly disabled and the page explicitly required an authorized reviewer; an administrator-tab read timed out before any approval action. No permission bypass, duplicate task submission, or second API/Worker chain was attempted.
- The current formal acceptance boundary is therefore: the root cause and code fix are verified, the pre-fix Edge symptom is reproduced, but v42 visual/date confirmation and the current task's approval-resume completion remain open pending a stable Edge control session. Protected sources and SOLVER_CT v1.0 remain untouched.

## v43 bounded approval audit and Edge control limitation

- The Runtime approval boundary was audited without touching the protected research runtime: teacher/admin identities may review Runtime work; a researcher may review only the declared academic research Agents; students and researchers cannot approve teaching work. The explicit plan-proposal API records the approver identity, role, scope, and state version before submitting the decision.
- Limited regression verification passed: launcher duplicate/parent-child/lock/reuse checks `7 passed`; Runtime approval roles plus administrator web contracts `8 passed`; external-evidence, empty-result, checkpoint-reload, and new-session UI contracts `9 passed`; student workspace contracts `3 passed`. All runs used `.venv\Scripts\python.exe -m pytest` and completed with only the existing dependency deprecation warnings.
- A fresh formal Edge connection was attempted once after the prior bounded failures. Edge connected, but reading the current tab list timed out and reset the browser connection. No approval action, second task submission, upload, or additional API/Worker instance was attempted. This remains an environment/control-layer blocker, not a product pass or a permission bypass.
- The v42 date-field fix remains code-verified but not visually confirmed after the asset-version bump. The current research task remains at the guest-visible `runtime_plan_proposal / approval_required` checkpoint until a stable Edge session and an authorized reviewer are available to complete the approval-resume read.
- Data analysis remains deliberately frozen: the capability is disabled, no data-analysis task was created, and no `RESEARCH_03` source or test was read, modified, or audited. SOLVER_CT v1.0 and all other protected boundaries remain unchanged.

## v44 evidence fallback and release-boundary consistency follow-up

- The evidence-card source path was re-audited. Local cards use the canonical Runtime evidence projection, pass the source fragment through `display_evidence_excerpt`, and render the exact bounded source string with `preserveRaw: true`; malformed or unsupported LaTeX is handled by the shared renderer's raw `<code class="math-latex-fallback">` path. The original-fragment contract is covered by the existing presentation tests, so the UI does not replace an unparseable formula with a lossy generic sentence.
- The external card path remains canonical-first: `external_retrieval.items` is preferred over the legacy view, evidence identity keys deduplicate DOI/arXiv/URL/title collisions, dates fall back from `date_label` to `updated_at`/`published_at`, and only validated `http`/`https` URLs become clickable links. Mock provenance is rendered with an explicit non-real-source label.
- A read-only consistency audit found and fixed a governance mismatch: `submission/contest_package/package_manifest.yaml` declared `demo_cases_included: true` while the enforced safety boundary was false. The manifest now declares `false`; the corresponding `BUG-20260809-002` backlog entry is resolved. `scripts/audit_readiness_consistency.py` now returns `status=consistent` with no errors. Demo materials remain excluded pending owner review.
- Bounded verification after this correction: evidence/presentation/UI contracts `18 passed`; routing and attachment contracts `42 passed`; config/readiness/approval contracts `14 passed`; launcher contracts `5 passed`. `scripts/validate_scenarios.py` returned `valid=true` for 6 catalog scenarios. No protected Runtime source or `test_research*` file was read or changed.
- Runtime release preflight remains intentionally fail-closed: no authorized paired structural suite or semantic sidecar is configured, and expected Agent/Runtime plan versions are not supplied. This is a release-evidence gap, not a reason to promote a Mock or synthetic result.
- Formal Edge remains incomplete in this round. A fresh Edge connection again timed out while reading the selected tab and reset the control session. No UI result was claimed from this attempt; v42 date confirmation, current research approval-resume completion, and formal structured-file upload remain open. The browser-control limitation has now repeated across bounded turns, while local service and contract verification continue independently.

## v45 formula-preservation correction and bounded full-suite result

- A further source-preservation audit found a concrete truncation risk: local evidence cards called `display_evidence_excerpt(..., max_chars=360)`, and the previous helper could cut a LaTeX formula at an arbitrary character boundary. That could remove a denominator, delimiter, or special symbol even though the original document remained intact.
- Non-protected fix: `apps/api/app/services/evidence_excerpt.py` now returns the complete raw fragment whenever formula/LaTeX markers are present; plain-text fragments retain the existing bounded card length. `apps/api/tests/test_task_presentation.py` adds coverage for a long formula fragment and confirms plain text remains bounded.
- Verification after the fix: the focused presentation/external/UI command reported `18 passed`; Ruff, Mypy, and front-end Node syntax checks passed. The UI still renders unsupported formulas through the raw `<code class="math-latex-fallback">` path.
- A bounded full Pytest run excluding all `test_research*` files enumerated 238 test files but exceeded 300 seconds and was terminated by the command timeout; no pytest process remained afterward. It is not claimed as passed. This timeout is retained as a release risk requiring per-file timing isolation, not a justification for a larger blind timeout.
- Formal Edge could not be re-established in this round: page inspection timed out at the browser-control layer. No new Edge result is claimed. v42 date confirmation, approval-resume completion, and structured-file upload remain pending stable Edge control.

## v46 data-analysis scenario freeze and single-instance recovery

- The product freeze was extended to the scenario registry boundary: `config/scenarios.yaml` now keeps `research_data_workbench_v1` with `enabled: false`. The UI capability and Task API were already fail-closed; this removes the remaining enabled scenario and readiness exposure. The catalog now reports 6 total definitions and 5 enabled scenarios, with no `RESEARCH_03` item in `/api/v1/scenarios`.
- Non-protected regression coverage was updated for the frozen scenario: the catalog test now verifies five enabled cases and rejects binding the frozen data-analysis scenario; the scenario API test verifies the frozen detail is HTTP 404 and readiness lists five scenarios. The catalog and freeze tests passed (`9 passed` and `2 passed` respectively); live API verification also returned five scenarios and `data_analysis.available=false, frozen=true`.
- During the controlled reload, the launcher command exceeded its bounded shell timeout and briefly left two project startup/API chains. Process inspection identified every PID by the exact project command line; only those confirmed project processes were stopped. Docker services were healthy afterward, and the existing launcher repair chain restored one API parent/child chain. No unknown listener, database, Redis, MinIO, or project data was removed.
- Final live readiness after recovery: `/health` HTTP 200 with database/Redis/MinIO `ok`; launcher doctor was not rerun after the repair chain's final recovery output, but the same live health and process inspection confirmed one API chain. This startup timeout is retained as an operational risk for future launcher hardening.
- Formal Edge remains unverified because the browser-control layer timed out before page inspection. No Edge pass is claimed. `RESEARCH_03` migration/audit has not started; protected Runtime source and `test_research*` remain untouched.

## v47 final bounded gates and freeze confirmation

- Final live startup verification: `team_launcher.py doctor --port 8000` passed `12/12`. Python/virtualenv, `.env`, Docker, postgres, Redis, MinIO, Qdrant, the project-owned single API chain, API reachability, and local-executor Worker policy all passed. `/api/v1/health` returned HTTP 200 with database/Redis/MinIO `ok`.
- The scenario-level data-analysis freeze is active in the live service: `/api/v1/scenarios` exposes five enabled scenarios, the frozen detail returns HTTP 404, and the capability projection reports `available=false, frozen=true`; no `RESEARCH_03` task was started.
- Final focused regression verification passed: formula/evidence presentation plus scenario catalog/freeze tests reported `32 passed`; the scenario API module reported `7 passed`. Ruff, Mypy, Node syntax checks, `git diff --check`, and the read-only readiness consistency audit passed. The audit status is `consistent` with no errors.
- Formula-card behavior now preserves the complete raw fragment whenever LaTeX/formula markers are present, including malformed or unsupported formulas; plain-text cards retain their bounded length. The raw fallback remains available to the browser, so unparseable formulas are shown as source rather than replaced or discarded.
- Protected boundaries were rechecked: no diff was found for `research_analysis_runtime.py` or `test_research*`; no `experiment_demo.csv`, raw `.local_inputs` YAML, student-private data, or SOLVER_CT v1.0 change was added.
- Formal Edge remains incomplete for this round. The browser-control layer timed out before page inspection, so v42 post-fix date rendering, approval-resume completion, and structured-file upload are not claimed as visually passed. Earlier valid Edge records for teacher/student/researcher/admin flows, pause/resume, stop, refresh recovery, evidence links, insufficiency, and routing remain recorded above.
- The bounded full non-research Pytest run remains incomplete: 238 test files exceeded the 300-second limit and were terminated with no residual pytest process. This is reported as a release risk, not as a pass.

## v48 Runtime migration follow-up and frozen-boundary regression

- A focused Runtime regression initially failed in `test_general_runtime_persists_retrieved_hits_for_result_presentation`. Root cause was the test fixture asking for `What is an agent?` while supplying a capacitor-voltage evidence hit. The relevance guard correctly rejected the unrelated hit as insufficient, so no `knowledge.hits` projection was produced. The test now uses the matching capacitor-voltage query; `test_general_question_runtime.py` passed `13 passed` and the production relevance behavior was unchanged.
- Core non-protected Runtime adapters passed their bounded tests: lesson preparation `10 passed`, assignment review `7 passed`, local knowledge QA `5 passed`, external research `9 passed`, and administrator web contracts `4 passed`. Teacher web contracts passed `2 passed`. The two frozen data-analysis migration boundary tests now assert HTTP 409 before Runtime/Legacy execution and passed `2 passed`; the old expectation of a queued RESEARCH_03 task was removed because it contradicted the explicit product freeze.
- The broader `test_runtime_task_execution_path.py` and `test_runtime_taskrunner_handoff_contract.py` modules remain unsuitable for a single broad run while they contain additional legacy RESEARCH_03 execution cases; their full run exceeded the bounded timeout. No protected source was read or modified, and no data-analysis task was started.
- Live post-test state remains healthy: `/health` HTTP 200, database/Redis/MinIO `ok`, local Mock provider explicitly reported as development configuration, and no Xingchen runtime call available. `/api/v1/scenarios` exposes five enabled scenarios; `data_analysis` remains `available=false, frozen=true`. The provider-free readiness projection returned `valid=true` with no errors.
- Formal Edge was retried through a fresh Edge connection and a new local tab, but tab discovery/navigation timed out and reset the browser control session. This round therefore adds no new visual claim. Earlier valid Edge evidence remains the source of truth for completed role flows; date-field post-fix confirmation, approval-resume completion, and structured-file upload remain open.
- Final code gates for this follow-up passed: Ruff, Mypy for `general_question_runtime.py`, Node syntax checks for workspace/admin/UI scripts, scenario validation, readiness consistency, `git diff --check`, and launcher doctor `12/12`. The timeout cleanup left no pytest process and did not alter the single API chain.

## v49 frozen-scenario governance alignment

- The data-analysis freeze exposed three release-script inconsistencies: commercial scenario validation, commercial route preflight, and contest-case validation all called the enabled-only catalog lookup for the frozen `research_data_workbench_v1`. They failed before reporting any result, even though the product freeze was intentional.
- Non-protected fixes make these validators inspect the complete catalog, skip disabled scenarios as auditable records, and validate only enabled execution paths. Reports now explicitly include `catalog_case_count` and `skipped_disabled_scenarios`; the frozen case is never routed or executed by these preflight commands.
- Verification passed: commercial validation reports `case_count=5`, `catalog_case_count=6`; commercial preflight routes 5/5 enabled cases with zero network/provider calls; contest validation reports 2 enabled cases out of 3 catalog cases; evaluation validation reports 82 synthetic cases with no private-publishable violations. The related pytest tests passed `2 passed` and `1 passed`; Ruff and Mypy passed for all changed scripts/tests.
- Additional gates passed: sensitive-file scan, readiness consistency audit, scenario validation (`6 total / 5 enabled`), and `git diff --check`. The service remains healthy with one API parent/child chain.
- Formal Edge remains blocked at tab discovery in the browser control layer. No new visual evidence is claimed; v42 date confirmation, approval-resume completion, and structured-file upload remain pending. RESEARCH_03 source migration/audit has not started.

## v50 frozen-config projection alignment

- A final configuration-audit mismatch was found: `scripts/validate_config.py` still reported the published RESEARCH_03 definition as runtime-available even though the product capability and scenario are frozen. The non-protected validator now projects `runtime_available=false`, `frozen=true`, and `unavailable_reason=data_analysis_frozen` for that agent when `DATA_ANALYSIS_ENABLED=false`; other agents retain their existing registry-derived status.
- Added `apps/api/tests/test_config_validation.py::test_frozen_data_analysis_is_not_reported_as_runtime_available`. The configuration-validation module passed `7 passed`, and Ruff passed for the changed validator and test.
- Final launcher doctor passed `12/12`; the single project API chain is `29504 -> 9832 -> 26084 -> 30072` (launcher repair parent, repair child, uvicorn parent, uvicorn child). No pytest process remains and no second project API/Worker chain is present. The other short-lived Python `-` processes shown by Windows process inspection are tool/test harness processes, not project launch commands.
- Formal Edge remains incomplete at tab discovery in the browser-control layer. No new visual claim is made. The broad non-research Pytest run and RESEARCH_03 migration/audit remain open risks; the protected Runtime source and `test_research*` files remain untouched.

## v51 shared evidence-card source action correction

- Static code audit found a concrete cross-role presentation defect: the shared `evidenceCard()` treated every non-empty `source_ref` as a local `kb://` document and always rendered the local-document action. Runtime evidence carrying a DOI, arXiv identifier, or public HTTP URL could therefore be mislabeled as “本地只读资料” and could not use the correct external source link from the shared card path.
- `apps/api/app/static/debug/workspace.js` now distinguishes `kb://` course evidence from external evidence. Local cards keep the course document viewer; DOI/arXiv/HTTP evidence gets a validated external link with `target=_blank` and `noopener noreferrer`; unsupported references explicitly show “无法打开原文” instead of a misleading local action. The existing external research card path remains canonical-first and unchanged.
- Added a focused UI contract covering local/external/unsupported actions. Verification passed: `test_unified_web_ui.py -k 'evidence or markdown'` reported `5 passed`; evidence/formula presentation tests reported `17 passed`; Node syntax and Ruff passed.
- Formal Edge visual verification is still pending because Edge tab discovery/new-tab control timed out again after a fresh browser connection. This fix is not counted as an Edge pass until the same evidence card is observed in the student, teacher, and researcher workspaces.
- The Workspace asset cache-bust was advanced to `20260814-evidence-card-links-v51` in `scripts/team_launcher.py` and `workspace.html`, with the student-page contract updated accordingly; this prevents a stale Edge asset from hiding the fix during the next visual run.

## v52 standalone student evidence deduplication and final bounded gates

- Static audit found a second presentation-path gap: the standalone student page combined `knowledge.hits` and `external_retrieval.items` directly, so the same DOI/URL/title could appear twice even though the shared researcher workspace already deduplicated its canonical external packet.
- `apps/api/app/static/debug/student.js` now merges those two source groups using evidence ID, source reference, normalized external URL, and normalized title identity keys. External DOI/arXiv/HTTP references remain clickable; local `kb://` references remain explicitly labeled as local course material; Mock references remain explicitly marked as non-real sources; raw excerpts continue through the formula-preserving Markdown path.
- Bounded verification passed: standalone student source/provenance contracts `2 passed`; shared evidence-card contracts `5 passed`; formula/evidence presentation contracts `17 passed`; Node syntax checks for student/workspace; Ruff for the changed web contracts; data-analysis freeze/catalog/API tests `18 passed`; `git diff --check`; sensitive-file scan; readiness consistency audit; and provider-free readiness projection.
- Live single-instance verification remains healthy: `team_launcher.py doctor --port 8000` reported `12/12`, `/api/v1/health` returned HTTP 200 with database/Redis/MinIO `ok`, and local-executor mode correctly reported no separate Worker requirement. No data-analysis task was started.
- Protected boundaries remain unchanged: no diff was found for `research_analysis_runtime.py` or `test_research*`; no SOLVER_CT v1.0, raw Xingchen YAML, student-private data, or `experiment_demo.csv` was added.
- Formal Edge visual verification is still not claimed. The in-app Edge control layer repeatedly times out at tab discovery/new-tab creation, so the current source-card deduplication and v51 external-link correction have only static/contract evidence in this round. Earlier valid Edge records remain recorded above; v42 post-fix date confirmation, approval-resume completion, and structured-file upload remain open.

## v53 bounded full-flow regression and stale-contract cleanup

- The shared evidence identity logic was tightened after review: evidence ID, DOI, arXiv, URL, and source path are authoritative identity keys; title is only a last-resort key when no stable source identity exists. This prevents two distinct sources with the same title from being silently collapsed. Both the shared workspace and standalone student page use this rule.
- The workspace cache-bust was advanced to `20260814-evidence-card-links-v53` in `scripts/team_launcher.py` and `workspace.html`; the student web contract was updated to require the new asset version.
- A real task API contract mismatch was found and corrected in tests: a teacher-only scenario had been submitted with the default student role, while the service correctly returned HTTP 422. The fixture now submits as `teacher`; `test_task_api.py` passed `6 passed`.
- Product freeze alignment was also completed in that module: three stale data-analysis execution tests now assert HTTP 409 and the explicit frozen response, with no task creation or execution. No data-analysis implementation was re-enabled, and no protected research test was changed.
- Bounded regression results: SSE basic events/reconnect/sequence `1 + 1 + 1 passed`; SSE event-order module `7 passed`; teacher web `2 passed`; administrator web and management `9 passed`; external research/runtime and retrieval `28 passed`; student evidence contracts `2 passed`; workspace evidence contracts `5 passed`. Node syntax, Ruff, and `git diff --check` passed for the touched web/test scope.
- The combined SSE run exceeded its 90-second limit and was stopped; its individual files were then run separately. No pytest process remained after cleanup. This is recorded as an execution-shape limitation, not a blanket full-suite pass.
- Formal Edge is still not visually verified: Edge discovery succeeds, but reading tabs and opening a fresh local page each timed out within bounded limits. Static/contract evidence must not be treated as the required Edge pass.

## v54 controlled task/SSE/runtime governance regression

- Runtime control coverage passed: task controls `4 passed`; approval roles and plan proposals `10 passed`; student/workspace control UI contracts `12 passed`; release preflight, launch policy, canary release, and release authorization `50 passed`.
- Task API coverage passed `6 passed` after aligning two stale expectations with current product boundaries: teacher-only scenario requests now use `user_role=teacher`, and the three data-analysis cases assert HTTP 409 frozen behavior instead of attempting execution. No frozen implementation or protected research test was enabled or modified.
- SSE coverage passed by bounded file-level runs: standard events `1 passed`, reconnect `1 passed`, event sequence `1 passed`, and event-order/reconnect scenarios `7 passed`. The combined multi-file run exceeded its 90-second cap and was stopped; no pytest process remained afterward.
- Teacher web contracts `2 passed`; administrator web/management `9 passed`; external research/runtime and retrieval `28 passed`. These are bounded backend/contract evidence only and do not substitute for the required formal Edge visual record.
- Release gates passed: Ruff on the changed scope, limited Mypy on `evidence_excerpt.py`, `team_launcher.py`, and `test_task_api.py`, JavaScript syntax checks, `git diff --check`, sensitive-file scan, readiness consistency, provider-free readiness, launcher doctor `12/12`, and live `/api/v1/health` HTTP 200. PostgreSQL/Redis/MinIO were `ok`; no pytest or Mypy process remained; one API parent/child chain remained.
- Live scenario projection exposes 5 enabled scenarios; the frozen data-analysis scenario is not enabled. `SOLVER_CT v1.0` baseline file is an existing frozen artifact and was not modified. No RESEARCH_03 migration/audit was started because the required real Edge verification is not complete and the user explicitly froze data analysis.
- Formal Edge remains the decisive open blocker: Edge is discoverable, but tab discovery and fresh-page navigation each timed out in bounded attempts. Therefore the overall objective remains incomplete; no claim is made that every frontend role, visual evidence card, approval-resume, file upload, or browser reconnect flow passed.

## v55 Edge control recheck and final state confirmation

- A fresh bounded Edge recovery attempt was made using the existing Edge extension binding. The browser family was discoverable, but both managed-tab listing and the subsequent browser-session recovery timed out; the control session reset before any page DOM or screenshot could be read. No UI interaction, task submission, approval, upload, or second service instance was attempted.
- This confirms the current limitation is at the Edge control layer, not an observed application response. The v51/v53 evidence-card fixes therefore remain code- and contract-verified but not visually accepted in this turn.
- Final live state after the attempt: `/api/v1/health` HTTP 200 with database/Redis/MinIO `ok`; the launcher-managed chain remains one project API parent/child chain; no pytest or Mypy process remains.
- The goal remains open. Formal Edge scenarios still requiring a stable browser control session include current student/researcher evidence-card inspection, teacher/admin visual flows, approval-resume, structured-file upload, refresh/session restoration, browser reconnect, and the complete per-scenario observation log.

## v56 formal acceptance matrix and launcher governance confirmation

- Added `docs/evaluation/formal_edge_acceptance_matrix_2026-08-14.md`. It records each requested role/scenario with user action, observed page state, Task/SSE evidence, duplicate/error/fake-success observations, refresh/session behavior, required fixes, and post-fix status. It explicitly separates historical formal Edge observations from backend/contract-only evidence and current blockers.
- Launcher governance was rechecked without changing the running chain: the persistent `29504 -> 9832 -> 26084 -> 30072` tree is one launcher repair parent/child plus one uvicorn parent/child chain. `doctor` does not leave a second service chain; the parent/child detector and single-instance lock tests protect this boundary.
- Governance regression passed `31 passed` for launcher behavior, including parent/child distinction, duplicate API handling, unknown-port refusal, safe repair behavior, frontend-version reuse, and actionable failure output. Frozen scenario/catalog tests passed `18 passed`. Node syntax and Ruff passed for the touched scope.
- Final verification passed again: `git diff --check`, sensitive-file scan, provider-free readiness (`valid=true`), readiness consistency (`errors=[]`), live `/api/v1/health` HTTP 200 with database/Redis/MinIO `ok`, and no pytest/Mypy residual process.
- Formal Edge remains the only decisive external-control gap. A fresh bounded attempt timed out at managed-tab discovery before any current v53 DOM could be read. The overall acceptance goal therefore remains open; no completion claim is made.

## v57 bounded Edge recovery, evidence-card validation, and final gates

- Edge control recovered on a clean local tab at `/student` without starting another API or Worker. The initial persisted checkpoint displayed `等待人工审批` and `本次没有可展示的资料依据`; after clicking `新建会话`, the old task disappeared and the `data_analysis` capability remained visibly disabled with `已冻结` and the message that new tasks are not accepted.
- A real student UI submission for `请解释电容电压连续性，并给出关键公式和课程资料依据` showed the bounded waiting states (`正在执行`, `正在等待模型响应`, `正在检索课程资料`) and disabled duplicate submission while running. It completed as `后备模型完成`, explicitly showing the fallback warning. The backend task was `task_eca1a3a67e14470bb890e2eca5bbb1ac`, status `completed`, agent `LEARN_01_LOCAL_RETRIEVAL_V1`, provider `local`, `fallback_used=true`, reason `route_cloud_unavailable`.
- The task event record contained one ordered sequence from `task.created` through `route.selected`, intent/plan, queue/running, agent progress, knowledge retrieval/context, answer/artifact creation, and `task.completed` at sequence 21. No duplicate evidence card appeared: the page showed exactly 3 cards (`S1`, `S2`, `S3`) and 3 `打开资料` actions, all for the same relevant course topic. Formula content remained visible as rendered math nodes; malformed/raw fragments were not replaced by the old “公式片段未完整解析” placeholder.
- Clicking `打开资料` first remained in `正在定位资料原文…` during the bounded observation window. A second real click completed with `完整原文 35,955–44,001 / 126,771 字符` and the note `原文中有 1 个公式按原始文本保留，未丢失内容`. Direct endpoint reproduction returned HTTP 200 with the same `kb://CT/.../第七章.md#chunk-131` source. This is recorded as a slow first-load observation, not a data-loss failure.
- After refreshing the same Edge page and allowing the existing session-history request to settle, the answer and 3 evidence cards were restored. Final DOM evidence: URL `/student`, `cards=3`, `sourceButtons=3`, answer status `后备模型完成`, evidence count `3`, frozen capability visible, and 42 rendered formula nodes. This confirms the unified `/student` → `workspace.html` session recovery path for this completed task.
- Final bounded gates after the Edge run: `test_student_web.py -k 'student_page_uses_unified_task_and_event_apis or standalone_student_source_cards_preserve_external_provenance'` passed `2 passed`; Ruff changed scope passed; Node syntax for `student.js` and `workspace.js` passed; `git diff --check` passed with only Windows line-ending warnings; sensitive-file scan passed; provider-free readiness returned `valid=true, errors=[]`; readiness audit returned `status=consistent`; launcher doctor returned `12/12`; `/api/v1/health` remained HTTP 200 with database/Redis/MinIO `ok`; no pytest or mypy process remained.
- The full acceptance goal remains open because the current Edge evidence is strongest for the student path and the historical records cover the other roles. Current v53 visual checks still do not constitute a fresh same-run pass for every teacher/researcher/admin path, approval-resume, structured-file upload, and external DOI/arXiv link. Data analysis remains intentionally frozen; no RESEARCH_03 migration or audit was started.

## v59 Formula preservation and final bounded review (2026-08-14)

- Edge recheck found a real evidence-card defect: in `preserveRaw` mode, unfinished `\\(`/`\\[` math could be heuristically cut into broken fragments. `apps/api/app/static/debug/ui-core.js` now sends only complete, structurally safe math to KaTeX; unfinished or unsupported formulas remain as the complete original text. The misleading incomplete-formula placeholder is no longer used for this path.
- After the fix, S1/S2/S4 closed formulas rendered correctly in Edge. S3’s incomplete fragment remained verbatim, including `{3} \\)`, with no information loss. The card still identifies local read-only material, and refreshing the session restored the four evidence cards and rendered formula nodes.
- The bounded student task control check showed waiting/running states, disabled duplicate submission, and recovery of the input after clicking Stop. Data Analysis remained visibly disabled/frozen; no data-analysis task was created.
- The final service state is one launcher-managed project chain, `/api/v1/health` HTTP 200, database/Redis/MinIO `ok`, and `team_launcher.py doctor --port 8000` `12/12`; `TASK_EXECUTOR_MODE=local` means no separate Worker. The stop command once timed out during cleanup; only the confirmed project stop chain was terminated, and no bare Uvicorn bypass was used.
- The event de-duplication fix remains valid: recovery appends a queued event only when an expired task was previously `RUNNING`; an already `QUEUED` task keeps its single durable `task.queued`. Recovery tests passed `2`; focused retrieval/presentation tests passed.
- Final bounded gates: Mypy reported no issues in 301 source files; Ruff, Node syntax, sensitive-file scan, and `git diff --check` passed. Formula/evidence/student Web tests passed `23`; recovery/topic-filter tests passed `4`. A combined 90-second test command and the SSE module remain explicitly recorded as bounded timeouts, not passes.
- Protected boundaries remain unchanged: no protected research Runtime or `test_research*` files read or modified, no `RESEARCH_03` migration/audit, no SOLVER_CT v1.0 change, and no sensitive/private/raw input artifacts added.
## v58 教师依据相关性修复与数据分析冻结确认（2026-08-14）

- 正式 Edge 教师端复测发现一个真实缺陷：查询“请为电容电压连续性设计一份45分钟课堂教案，包含目标、流程和形成性评价”时，资料卡片错误包含“电压源支路”和“电容的串联与并联”章节。根因是教学意图的主题门禁只要求标题命中任意一个二字词，导致“电压”或“电容”的弱命中被当作完整主题相关。
- 修复 `RetrievalContextService`：教学意图会剔除教案结构词，并要求复合主题至少命中两个独立主题锚点；新增回归用例证明电压源单命中和电容单命中均被过滤，完整“电容电压连续性”主题才可作为依据。该修复不触碰受保护的 `research_analysis_runtime.py` 或 `test_research*`。
- 修复后的非受保护检索回归 `apps/api/tests/test_retrieval_context_packet.py` 为 7 passed；资料/公式/外部来源展示回归为 13 passed；学生 Web 冻结/公式/证据子集为 2 passed；配置与场景回归为 16 passed。
- Edge 复测期间曾观察到旧进程仍返回旧卡片；按单实例启动器的项目进程链识别安全重载后，旧代码被确认不是新结果。重载期间手动裸 Uvicorn 曾因未注入项目 `.env` 返回依赖 unavailable，已停止该非规范进程并恢复启动器链；最终 `/api/v1/health` 为 200，database/redis/minio 均为 `ok`，provider 明确为本地 `mock`。
- 最终项目进程链为 launcher `21540 -> 11600`、Uvicorn `10072 -> 12276`，仅一条 API 链；`TASK_EXECUTOR_MODE=local`，无独立 Worker。`team_launcher.py doctor --port 8000` 为 12/12。
- 数据分析按用户要求继续冻结：Edge 能力卡片保持 disabled/“已冻结”；冻结回归 2 passed；新建数据分析任务返回 HTTP 409，现有历史任务/数据不修改；未启动、未读取、未迁移或审计 `RESEARCH_03` 受保护路径。
- 较大的 `test_student_web.py + test_unified_web_ui.py + test_teacher_web.py` 组合在 90 秒限时内未结束，已停止并记录为未完成验证，未以超时结果冒充通过。正式 Edge 的学生完成/刷新恢复已留有记录；教师本轮发现的旧资料卡片缺陷已完成代码级修复，但修复后 Edge 任务在限时窗口内进入 Runtime checkpoint/等待人工审批，未把未完成状态写成最终通过。
## v60 教案检索候选修复与审批恢复复核（2026-08-14）

- A fresh formal Edge teacher submission used the prompt `请为电容电压连续性设计一份45分钟课堂教案，包含目标、流程和形成性评价`. The visible page entered the normal bounded waiting state and exposed the stop control while the task was running; no duplicate submission was made.
- The previous zero-evidence result was traced to the published `TEACH_01_LESSON_PREP_V1` retrieval policy: textbook chunks classified as `mixed` or `unknown` were excluded before the topic-relevance gate. The policy now allows those two bounded content types. `RetrievalContextService` remains the final gate and still rejects single-anchor weak matches, so this does not broaden evidence to unrelated capacitor/voltage chapters.
- The backend Runtime record for the Edge-created task `task_4aadeb43d3e64458a05a2a06bdafaa3b` reached `waiting_review`; `lesson.retrieve` recorded three evidence IDs (`S1`, `S2`, `S3`) and three source refs, all titled `2. 电容电压连续性`, with `evidence_status=partial`. The authorized approval transition then queued and completed the same task without a second API/Worker chain.
- After approval recovery, the persisted result contained three `structured_result.knowledge.hits` entries, all titled `2. 电容电压连续性`; formulas remained present in the structured math output. Task events were contiguous `1..29` with `29` unique sequences and no duplicate event sequence.
- The Edge control session timed out while reading the final old-tab DOM after the approval transition. Therefore this round claims the Edge submission/waiting-state observation plus backend approval-recovery evidence, but does not claim a new final post-approval Edge visual card read. Earlier same-identity Edge approval, refresh recovery, formula preservation, researcher-link, stop, and admin task-center records remain the valid visual evidence in this report.
- Bounded checks after the reload: focused registry/retrieval tests `12 passed`; `scripts/team_launcher.py doctor --port 8000` returned `12/12`; `/api/v1/health` returned HTTP 200 with database, Redis, and MinIO `ok`; the launcher reported one project API chain and no separate Worker because `TASK_EXECUTOR_MODE=local`.
- No protected `research_analysis_runtime.py` or `test_research*` file was read or modified, no `SOLVER_CT v1.0` change was made, and data analysis remains visibly frozen with no `RESEARCH_03` task started.

## v61 正式 Edge 研究者与管理员复核（2026-08-14）

- 正式 Edge 研究者工作台以游客会话提交了主动学习/工程教育问题。页面真实进入识别、计划、能力编排和外部检索状态，最终显示“当前主题暂无可核验证据”。后端任务 `task_936e65bd57664ea08c5e668195c6399e` 为 `completed`，Runtime 节点 `research.intent`、`research.fetch`、`research.answer`、`research.verify` 均成功；事件序列为 `1..26`，26 个唯一序列，无重复。该结果不是静默成功：fetch 记录了 OpenAlex HTTP 500、arXiv 限流，以及 Crossref 候选因主题不匹配或缺少摘要被拒绝，页面正确保留证据不足提示。
- 同一 Edge 会话以更窄问题 `检索关于 retrieval augmented generation 在工程教育中的最新研究，返回 DOI 或 arXiv 链接` 复测。页面展示 `外部证据 · 论文 6`，每张卡包含标题、发表日期、来源、作者、摘要、证据 ID 和 DOI/原文入口；后端任务 `task_6cb49e22538c44ceaf449c4032610442` 为 `completed`，`external_retrieval.items=6`、`external_search_view=6`、`external_references=6`，review status 为 `approved`。这是一次真实 Edge 结果，不是静态/API 替代。
- 点击第一张 `打开论文` 后，Edge 新标签实际打开 `https://publikasi.dinus.ac.id/jcta/article/view/17084`，页面标题与论文标题一致。由此确认 DOI/HTTP 外链能从证据卡投影并打开；其余卡也各有 DOI 链接。来源结构、页面卡片和后端 `external_references` 数量一致，无重复证据卡、无伪造成功提示；页面同时显示“请打开原文核验”。
- 研究者首轮空结果与第二轮有证据结果共同覆盖了“数据不足/异常结果”和“资料依据、摘要、作者、期刊、可核验链接”两类验收边界。首轮没有错误日志吞掉失败，第二轮完成后再读取资料依据面板，证据条目和链接均可见。
- 正式 Edge 新标签访问 `/admin`，未猜测或使用凭据。页面真实显示管理员登录表单、“游客模式”和“当前账号没有管理员权限”，未向游客泄露账号、会话、审计或系统控制数据。历史已记录的管理员认证/任务中心证据仍保留；本次新增的是游客权限边界复核，不冒充已认证管理员通过。
- 本轮不修改数据分析，不启动 `RESEARCH_03`，不新增 API/Worker。数据分析继续保持页面 disabled/冻结和 HTTP 409 边界；保护路径、`SOLVER_CT v1.0`、敏感文件边界保持不变。

## v62 最终门禁结果（2026-08-14）

- 通过：Ruff changed scope；Mypy changed scope（5 files）；外部研究 runtime/retrieval `28 passed`；单独运行的 `test_agent_registry.py` `5 passed`；单独运行的 `test_retrieval_context_packet.py` `7 passed`；`git diff --check`；敏感文件扫描；`team_launcher.py doctor --port 8000` `12/12`；`/api/v1/health` HTTP 200，database/Redis/MinIO 均为 `ok`；保护路径 diff check passed。
- 未完成且不记为通过：排除 `test_research*` 后的全量 pytest 达到 180 秒上限；contracts/web 合并回归达到 90 秒上限；单独的 data-analysis freeze 和 task API 命令未在限时窗口内干净退出。过程中确认并清理了仅属于本轮 pytest 的残留进程；没有清理 API/Worker。部分命令在超时前已输出测试通过行，但由于最终退出码为 124，按门禁规则不计为通过。
- 这组 pytest 超时目前表现为测试进程/fixture 退出不干净，而非已定位为业务断言失败；应在后续专门拆分 fixture 生命周期和退出钩子后再修复，不能用更长超时掩盖。正式 Edge 证据、外部研究 28 项和本轮静态/运行时门禁均不依赖把这些超时冒充通过。
- 单实例最终状态仍为 launcher 管理的一条 API 父子链；`TASK_EXECUTOR_MODE=local`，无独立 Worker。数据分析冻结，`RESEARCH_03` 迁移/审计仍未开始。
## v63 证据元数据一致性修复与最终教师 Edge 复核（2026-08-14）

- 修复了 Runtime 内存结果漏应用证据元数据，以及 TaskRunner 最终投影用空的 legacy 候选列表覆盖 `knowledge_hit_count` 的问题。现在 `knowledge.hits`、`evidence_status` 与 `knowledge_hit_count` 保持一致。
- `TaskRunner.shutdown()` 纳入后台 evidence ingest task 的取消清理；新增可靠性测试确认关闭时不会遗留后台任务。未读取或修改受保护的 `research_analysis_runtime.py` 与 `test_research*`。
- 变更文件：`apps/api/app/services/general_question_runtime.py`、`apps/api/app/services/task_runner.py`、`apps/api/tests/test_general_question_runtime.py`、`apps/api/tests/test_task_executor_reliability.py`。

### 最终正式 Edge 教师流程

- 正式 Edge `/workspace?role=teacher` 新建会话并提交课堂教案任务。页面经历识别、计划和运行中等待状态，发送按钮运行期间禁用，没有重复提交。
- 任务 `task_f4c6940148a8408581b5903c13234106` 经同一任务的授权审批过渡后完成；游客界面没有审批按钮，因此审批由 API 控制，不冒充 Edge 点击审批。后端最终记录：`completed | knowledge.hits=3 | evidence_status=partial | knowledge_hit_count=3 | TEACH_01_LESSON_PREP_V1`。
- 任务事件连续为 `1..29`、29 个唯一 sequence；没有实际非空的 `error`/`error_message` 字段。Edge 显示“带提示完成”“教案设计 · 电路理论”“需要教师确认”。
- “查看资料依据”显示 3 张 `S1/S2/S3` 卡片，均为 `2. 电容电压连续性`、电路理论、`mixed`；证据面板含 16 个 math 节点。S3 的残缺原文 `m{d}u}` 原样保留，没有出现“公式片段未完整解析”占位符。点击第一张“打开资料”可进入本地只读原文并看到公式与上下文。
- 刷新同一 Edge 页面后，当前任务、3 个资料卡标签、公式节点和 S3 原文仍在 DOM 中，未出现公式不完整占位符。验收结束时已安全释放 Edge 会话，没有留下第二个 API/Worker。

### 本轮验证与剩余风险

- `pytest apps/api/tests/test_general_question_runtime.py apps/api/tests/test_lesson_prep_runtime.py --no-cov -q -s`：`23 passed`；Ruff 通过；Mypy 对 2 个生产文件 `Success: no issues found`。
- 既有 bounded 回归仍有效：freeze `2 passed`、task API `6 passed`、student web `11 passed`、teacher web `2 passed`、admin web/management `9 passed`、external research/retrieval `28 passed`、registry `5 passed`、retrieval context `7 passed`、shutdown focused `1 passed`。完整非研究 Pytest 没有宣称通过；Windows capture 模式曾达到上限，关键模块已用 `-s` 逐文件限时验证。
- `git diff --check`、敏感文件扫描、受保护路径 diff 检查通过；`team_launcher.py status` 为 ready；最终 `team_launcher.py doctor --port 8000` 为 `12/12`，单实例 API PID 14884，`TASK_EXECUTOR_MODE=local` 无独立 Worker；`/health` HTTP 200 且 database/Redis/MinIO 为 `ok`。
- 尚未补齐管理员认证态、结构化文件上传、浏览器断开重连、全部停止/审批变体及每个角色的空/异常矩阵。数据分析按要求冻结，不能通过启动 `RESEARCH_03` 补测；最短下一步是保留当前单实例，先补齐这些非数据分析 Edge 路径，再拆分运行完整非研究测试。
## v64 学生证据包一致性与研究工作台 Edge 收尾复核（2026-08-14）

- 学生端正式 Edge 新任务发现第二个真实投影问题：页面已有 3 张正确资料卡，但旧流程只持久化 `evidence_view`，`knowledge_hit_count` 为 0，`evidence_packet` 为 `not_run/unavailable`。根因是最终展示层没有把旧流程的 `WorkflowContextBundle` 或 legacy `core_retrieval_summary` 同步到统一证据包。
- `TaskResultPresentationService` 现在在最终展示边界统一同步 `knowledge_hit_count`；对有 WorkflowContext 的结果生成完整 v1 evidence packet，对无 bundle 但已有证据卡的旧结果从卡片重建来源元数据。保留原始摘要/公式，不用文案掩盖缺失来源。
- 新增 bundle 与 legacy 两条回归测试。`test_task_result_presentation.py` 与 `test_task_presentation.py` 共 `24 passed`；Ruff 和生产文件 Mypy 均通过。

### 学生端最终 Edge 复测

- 任务 `task_87685b054fa0404bbaf62a5795a979b8` 路由到 `LEARN_01_LOCAL_RETRIEVAL_V1`，最终后端为 `completed | knowledge_hit_count=3 | evidence_status=partial | evidence_view=3 | evidence_packet.sources=3 | retrieval_status=ready`。
- Edge 显示 3 张本地资料卡、61 个 math 节点、明确“本地只读资料”标签；没有“公式片段未完整解析”占位符，没有 Mock 伪装。刷新后仍恢复 3 张卡片和 61 个公式节点。SSE 为 `1..19` 唯一连续 sequence，错误字段为空。

### 研究工作台与停止任务 Edge 复测

- 研究任务 `task_335c09aa51d2412d8798879303fd17dd` 路由到 `RESEARCH_01_ACADEMIC_SEARCH_V1`，后端为 `completed`，`external_retrieval.items=6`、`external_search_view=6`、`external_references=6`，事件 `1..27` 连续且无错误。Edge 显示外部证据论文卡片，未标为本地资料；6 条 DOI 链接可见。
- 点击第一条“打开论文”实际打开 `https://publikasi.dinus.ac.id/jcta/article/view/17084`，页面标题和论文标题可见。刷新研究工作台后 6 条论文链接、DOI 信息和外部来源标签均恢复。
- 另一个受控研究任务 `task_ce304fcfd69d4cf3833354b29bc2aea1` 在运行中由 Edge 点击“停止”，页面显示“已停止/未生成新结果”，没有假完成；后端最终 `cancelled`，事件 `1..26` 唯一连续，包含 `cancel.requested` 与 `task.cancelled`。

### 当前结论

- 资料依据在学生端、教师端和研究端的主要显示路径已完成真实 Edge 复核；本地课程资料、外部 DOI/网页来源、公式保留、刷新恢复、来源去重和停止边界均有本轮或前轮实证。
- 仍未完成的项目级路径：管理员认证态的完整错误详情复测、结构化文件上传的正式 Edge 成功记录、浏览器断开/重连，以及完整非研究 Pytest 全量无超时退出。数据分析继续冻结，`RESEARCH_03` 迁移/审计尚未进入处理阶段。
