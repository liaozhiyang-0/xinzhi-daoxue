# 芯智导学完整验收跟进记录（2026-08-13）

本记录只汇总本轮实际执行过的自检、测试和正式 Edge 操作。Mock/local 结果保持显式标记，不将其描述为星辰真实调用结果。

## 1. 启动稳定性与基础设施

- 当前分支：`codex/auth-foundation`。
- 本轮只保持一条项目启动链：launcher → uvicorn parent → uvicorn reload child；`TASK_EXECUTOR_MODE=local`，因此没有独立 Worker。
- `scripts/team_launcher.py doctor --port 8000`：12/12 通过。
- API health：`status=ok`，database/redis/minio 均为 `ok`，active provider 为 `mock`。
- `check_runtime_readiness_projection.py`：`provider_free=true`、`valid=true`、无 errors。
- `validate_config.py`：`valid=true`。
- `validate_scenarios.py`：`valid=true`，6 个 scenario 全部启用。

启动器边界测试实际通过：

- 数据库/Redis/MinIO 未就绪报告；
- reload 父子进程不误判为重复实例；
- 独立 API 链被识别为重复实例；
- Worker 父子进程去重；
- 修复失败输出可行动原因；
- 单实例锁拒绝第二次本地 API 启动；
- 已运行 API 被复用；
- 重复的项目 API 链被安全重启。

## 2. 正式 Edge 验收

Edge 使用本地正式界面 `http://127.0.0.1:8000`，没有以 API 或静态测试替代页面操作。

### 学生端课程资料问答

- 操作：进入学生工作台 → 访客入口 → 课程问答 → 输入“为什么电容电压不能突变？” → 提交。
- 页面表现：`带提示完成`；显示“使用 2 条课程资料”和“本回答有直接课程资料支持”。
- 任务落库：`completed / CT / general_qa / LEARN_01_LOCAL_RETRIEVAL_V1`。
- 资料依据：显示 2 张唯一资料卡，均标记为本地只读资料；打开资料后能定位到电容电压连续性原文上下文。
- 限制提示：原文窗口明确提示有 7 个公式片段未完整解析，需要人工核对；本轮不把该资料宣称为完整公式渲染。
- 刷新复测：刷新后任务状态、回答和 2 张资料卡仍在。
- 新建会话复测：旧会话资料卡未残留，新会话为空状态显示“本次没有可展示的资料依据”。

### 管理员/教师审批恢复

- 操作：Edge 管理员页面登录 → 创建 CT lesson task → 等待审批 → 提交审批。
- 页面表现：审批按钮可见且可用；审批后显示 `带提示完成`、`已完成`、课程计划和“已检索 5 条课程资料”。
- 任务落库：`completed / CT / lesson_prep / TEACH_01_LESSON_PREP_V1`。
- 事件：包含 `approve_requested`，最终为 `task.completed`。
- 该复测验证了 runtime-control 权限投影对教师/管理员跨用户任务的修复。

### 研究者工作台

- 操作：新建会话 → 学术检索 → 提交“检索近五年关于主动学习对工程教育效果影响的学术证据，返回可核验来源并标出证据限制”。
- 任务落库：`completed / UNKNOWN / academic_search / RESEARCH_01_ACADEMIC_SEARCH_V1`。
- 后端事件序列：按 sequence 单调递增，从 `task.created`、`route.selected`、`external_retrieval.started/completed` 到 `artifact.created`、`task.completed`；没有同 sequence 重复事件。
- 当前轮限制：提交后 Edge 最终 DOM 读取连续超时，因此本记录不把本轮研究结果卡片的最终可见状态作为新证据。此前已完成的 Edge 研究证据（唯一来源链接、arXiv/DOI 打开、刷新和新会话行为）应与本限制一起解读。

### 未完成的页面验收

本轮没有把以下项目标记为通过：教师作业批改完整链、长时间等待提示、停止任务、停止后审批恢复、空结果/异常结果、数据不足提示、多领域任务全量路由矩阵，以及管理员全部模块的逐项业务操作。它们需要下一轮逐项建立“操作—页面—任务状态—事件—日志—复测”记录。

## 3. 代码与验证结果

- 资料页修复：优先使用当前证据 anchor，避免 stale chunk anchor 覆盖；带 chunk 时限制上下文窗口。
- runtime-control 修复：教师/管理员审批控制使用与审批接口一致的任务权限投影。
- `test_task_presentation.py`：17 passed。
- runtime-control contract：9 passed。
- 启动器关键边界用例：7 passed。
- Ruff（虚拟环境模块入口）：通过。
- Mypy（tasks.py、knowledge.py）：通过。
- `node --check apps/api/app/static/debug/workspace.js`：通过。
- `git diff --check`：通过（仅报告 CRLF 转换提示）。
- 受保护的 `research_analysis_runtime.py` 无 diff；冻结基线和禁止提交路径未进入本轮变更列表。

## 4. 风险与最短下一步

1. 当前配置为 development/mock，`xingchen_runtime_available=false`；不能把本轮结果当作真实星辰生产验收。
2. `RESEARCH_03_DATA_ANALYSIS_V1` 仍需保持显式 opt-in，不进入核心迁移完成结论。
3. 课程资料中公式解析存在人工核对提示；资料窗口可能包含同一文档的相邻上下文，需继续收紧 section-level 证据边界。
4. 全量 pytest 和 knowledge API 证据测试本轮出现超时，未宣称全量通过；应单独定位测试夹具/数据库初始化阻塞。
5. 发布前仍需补齐版本策略、route audit、checkpoint/重连测试、灰度开关及完整 Edge 角色矩阵。

最短下一步：保持单实例，先定位 knowledge API 测试超时，再按学生停止/等待/审批恢复、教师作业批改、研究者刷新/空结果、管理员模块四组完成 Edge 复测；最后重新跑全量 Ruff、Mypy、Pytest 和发布门禁。

## 5. 资料依据专项复测补充

## 6. Edge relevance and insufficient-evidence follow-up

- Edge research task `task_11515a2847d446af9c73dccb9705598e` completed through `RESEARCH_01_ACADEMIC_SEARCH_V1`. The UI showed two external evidence cards after deterministic filtering; both had clickable arXiv links and the provenance label `外部来源 · 请打开原文核验`. Nursing, mathematics, and Google Summer of Code candidates observed in the earlier run were no longer displayed.
- The first empty-topic run exposed a remaining safety defect: the answer said the six retrieved papers were unrelated but still displayed them as evidence cards. The fix now requires every explicit compound topic term to occur in the evidence title or abstract before display.
- Edge retest task `task_40feff9720f0454d840a55d027117585` completed with zero external evidence cards and a visible `证据不足` marker for the deliberately unsupported quantum-coral topic. This prevents unrelated retrieval candidates from being presented as supporting evidence.
- The two retained engineering-education candidates are adjacent active-learning-equivalent methods (project-based/collaborative learning), not proof that every retained paper directly measures active learning. The UI still requires opening the original paper for verification.
- After the final Edge retest, the single launcher/API chain was stopped by its exact parent-child PID tree; port 8000 was released and no project API/Worker process remained.
- Final bounded verification: Ruff (app and tests, excluding protected research files) passed; Mypy passed for the changed API and external-research files; `node --check` passed; `git diff --check` reported only existing LF/CRLF conversion warnings. The non-protected pytest collection was run with a 120-second bound but timed out before completion and is not claimed as passed.

## 7. Core workflow Edge follow-up

## 8. Latest Edge approval recovery retest

- The v4 admin page was loaded in real Edge after starting one launcher chain. The task detail rendered a compact summary with `waiting_review`, `TEACH_01_LESSON_PREP_V1`, `lesson-prep-v1`, 21 events, and contiguous sequence confirmation; the full JSON was deferred behind an explicit expand button.
- The admin action was completed through the page: `submit approval` -> inline `confirm approval`. The visible task detail changed to `running`; the refreshed admin task list later showed `completed`.
- Database/debug evidence for `task_8db4fda5fb13403a98242bb59835ae3c`: final status `completed`, event count 29, sequences 1-29 without duplicates, including the approval decision, `artifact.created`, `agent.output`, and `task.completed`. The event payload records `approver_role=admin`; the provider remains local/mock and is not described as a real Xingchen result.
- The teacher page was refreshed for final result display, but two small DOM reads timed out in the Edge control layer. Therefore the backend completion and admin-list result are verified, while teacher-side post-approval answer rendering remains an open UI verification item.

## 9. Latest bounded verification and release state

- `node --check apps/api/app/static/debug/admin.js` and `node --check apps/api/app/static/debug/workspace.js`: passed.
- Ruff on the changed API/services/tests: passed. Mypy on the changed API and external-research files: passed.
- `pytest -q apps/api/tests/test_admin_web.py --no-cov`: exceeded the 60-second bound and was stopped; the test process was then confirmed and terminated. It is not claimed as passed. The timeout needs separate fixture/database initialization diagnosis.
- A single-test `--setup-show` rerun of `test_admin_and_login_pages_are_available` also exceeded a 45-second bound before setup output, so the blocking point is before the test body (likely app/TestClient fixture initialization or import-time startup). The process was checked afterward; no project service was left running.
- `git diff --check`: exit 0 with only existing LF/CRLF conversion warnings. Sensitive-path scan was empty; no protected research runtime/test, frozen baseline, `.local_inputs`, or experiment demo file entered the changed-file list.
- After the Edge retest, the exact launcher/API process tree was stopped. Port 8000 is released and no project API/Worker process remains.

- Student stop scenario: Edge submitted an academic-search task `task_8ca6c31cb4b0476981857ad7bd0a6ce3`, clicked `停止`, and showed `已停止`, `未生成新结果`, and `本次任务已停止，未生成新的资料依据`. The database ended at `cancelled`; events were sequences 1–26 with no duplicate sequence values. Refresh preserved the cancelled state and zero evidence cards; a new session cleared the question and stopped state.
- Teacher lesson scenario: Edge submitted a 45-minute capacitor-voltage-continuity lesson request as a teacher guest. Task `task_8db4fda5fb13403a98242bb59835ae3c` routed to `TEACH_01_LESSON_PREP_V1` and entered `waiting_review`, with the page showing the 100-second waiting notice and the checkpoint reason requiring an authorized reviewer. Admin Edge login and the task-center inspection succeeded; the admin detail showed the task, route, runtime `lesson-prep-v1`, five retrieval sources, and contiguous event sequence 1–21.
- Admin UI gap found and patched: the admin task detail was read-only even though the existing backend already exposed the authorized `POST /api/v1/tasks/{task_id}/approve` path. `admin.js` now exposes approval only for an authenticated admin and a `waiting_review` task, refreshes the list/detail after approval, and reports errors. The page uses cache-buster `20260813-admin-task-approval-v3`.
- Admin approval is not marked passed: Edge automation was blocked first by the original native confirmation dialog and then by repeated large-detail page timeouts after the page-side confirmation change. Database evidence confirms no approval request was submitted; the task remains safely `waiting_review`.
- Follow-up fix for the Edge timeout: the admin task detail now renders a compact summary first (task status, route/Agent, Runtime version, evidence count, event count, and contiguous-event check) and defers the full execution JSON until `查看完整执行链` is clicked. The cache-buster is now `20260813-admin-task-approval-v4`. This preserves the full audit payload while preventing the initial DOM from being blocked by a very large `<pre>`.
- Static validation after the patch passed: Ruff, Mypy, `node --check` for admin/workspace JavaScript, and `git diff --check` (CRLF warnings only). Two bounded pytest attempts timed out before reliable completion; no pytest process remained afterward.

本轮以正式 Edge 工作区提交了新的 CT 课程问答和新的学术检索任务，均只提交一次。

- CT 任务 `task_dd0996d7e82b4bedbc9fbe1d087bba73`：`completed`，`LEARN_01_LOCAL_RETRIEVAL_V1`。页面显示 2 条课程资料，S1/S2 均为“2. 电容电压连续性”，摘要与问题相关；结果明确标记“后备模型完成”，公式片段提示人工核对。
- 学术检索任务 `task_2cb96eb39471439394fc2efb9698ad40`：`completed`，`RESEARCH_01_ACADEMIC_SEARCH_V1`。后端事件序列完整，外部检索持久化 3 条 canonical evidence：Crossref DOI、OpenAlex DOI、arXiv URL，均 `mock=false`。检索 warnings 明确记录 topic mismatch 候选被拒绝以及“仅展示本地范围候选，需人工核验”。
- 发现并修复前端投影根因：当 `external_retrieval.items` 与旧 `external_search_view` 同时存在时，前端原先优先旧 view，可能导致历史回答中的 evidence ID/标题/摘要与 canonical 来源错位；现在 canonical retrieval 优先，旧 view 仅作 legacy fallback。
- 去重现在同时使用 DOI、arXiv、规范化 URL 和标题身份，覆盖“同 DOI 不同 URL”和“arXiv abs/pdf URL”重复形态。
- `workspace.html` cache-buster 更新为 `20260813-evidence-projection-v26`，确保 Edge reload 获取本次修复脚本。
- 专项契约测试、旧投影兼容测试、Ruff、Mypy、JS 语法检查均通过。
- Edge 在长研究结果 DOM 读取和完整 `test_student_web.py` 上仍出现超时；因此 DOI/arXiv href 的本轮最终页面点击证据、学生页面测试全量通过均未宣称完成。此前已获得的研究页面来源可见性证据仍需结合本限制解读。
