# 资料依据投影与 Edge 复测补充记录（2026-08-13）

本记录只覆盖本轮资料依据问题，不代表所有业务路径或发布门禁均已完成。

## 根因

直接学术检索结果由同一个 `ExternalRetrievalResult` 生成两类数据：

- `external_search_view`：给前端来源卡片使用；
- `external_retrieval.items`：给任务呈现、来源统计、质量提示和会话恢复使用。

旧代码在直接检索结果构造处只保存了前者，导致实时卡片可能有来源，而任务摘要、来源计数和刷新后的呈现仍按“没有外部证据”处理。历史任务还可能只有旧的 `external_search_view`，因此单纯修复新任务仍不能保证恢复一致。

## 修复

- `apps/api/app/services/task_runner.py`
  - 直接学术检索结果同时保存规范化 `external_retrieval` 包和 `external_search_view`。
  - 两者都来自同一个 `ExternalRetrievalResult`，不重新拼接来源字段。
- `apps/api/app/services/task_presentation.py`
  - 对旧任务仅有 `external_search_view` 的结果建立受限兼容投影。
  - 任务摘要、外部来源分类和“已检索/资料不足”判断因此与历史卡片保持一致。
- `apps/api/app/static/debug/workspace.js`
  - 外部证据去重优先使用规范 URL、DOI、arXiv ID、标题，再回退到 evidence ID，避免跨 Provider 重复卡片。
- `apps/api/tests/test_external_search_and_fetch.py`
  - 锁定新直接检索结果同时持久化 `external_retrieval.items`。
- `apps/api/tests/test_task_presentation_external_legacy.py`
  - 覆盖旧结果仅有 `external_search_view` 时的恢复呈现。
- `apps/api/app/services/external_research_answer.py`
  - 对明确的“电子信息/电子工程 + 课程/教育/辅导”请求增加领域过滤，避免护理、英语教育或泛哲学来源与电子信息课程直接证据混在同一层。
  - 新增测试锁定跨学科来源会被排除。
- `apps/api/app/static/debug/workspace.js`
  - 外部卡片增加来源溯源提示；仅真正标记为 `mock`/`development_mock` 的来源显示“开发态 Mock · 非真实来源”，真实 OpenAlex/Crossref 来源显示需打开原文核验。

## 实际验证

- `test_external_search_and_fetch.py` + `test_task_presentation.py`：32 passed。
- 兼容投影新增测试 + `test_external_search_and_fetch.py`：16 passed。
- Ruff：通过。
- Mypy（`task_runner.py`、`task_presentation.py`）：通过。
- `node --check apps/api/app/static/debug/workspace.js`：通过。
- API 启动后真实 `/api/v1/health`：database、Redis、MinIO 均为 `ok`；曾确认单监听实例。
- Docker Compose 依赖：postgres、redis、minio healthy，qdrant running。
- 新过滤逻辑验证：`test_external_search_and_fetch.py` 16 passed；Ruff、`node --check` 通过。
- 统一检索出口直接异步验证：模拟 OpenAlex/Crossref 混合结果时只返回 `electronics-education`，`approved_count=1`，并记录 `cross-topic evidence was removed before display`。

## Edge 记录

- 之前已完成的 Edge 证据卡片、arXiv 链接、刷新/恢复、空证据和 Mock 标记记录仍见 `runtime_edge_evidence_2026-08-12.md` 与 `runtime_edge_evidence_2026-08-13.md`。
- 本轮后端修复后的新 Edge 页面导航未能完成：Edge 控制层多次在本地工作台导航阶段超时，服务端未收到对应的新页面 GET 请求；因此不能宣称本轮修复已经通过正式 Edge 复测。
- 启动日志显示首次预热会加载 SentenceTransformer，耗时约 33 秒；这会放大首个页面导航的等待窗口，但尚未证明它是证据错位的根因。
- 超时测试命令曾留下第二条项目启动链和 pytest 子进程，已按精确命令行/PID 清理；最终审计时 8000 端口无监听、无项目 API/Worker/pytest 残留。
- 本轮再次只启动一条链：Docker 依赖 healthy，Uvicorn 完成启动，真实 `/api/v1/health` 返回 200；随后 Edge 扩展在 `tabs.list()` 和新标签创建阶段再次超时并重置控制内核。该次启动链已精确停止，最终 8000 端口无监听、无项目进程残留。

## 未完成与风险

- 需要在 Edge 控制层恢复后，用同一个单实例重新完成：新学术检索、来源卡片逐字段核对、链接点击、刷新、切换会话、学生端/教师端一致性。
- 统一 Web Pytest 在 180 秒限时内未返回并产生残留进程，不能计为通过；应单独限时、串行定位其阻塞原因。
- 审批后恢复仍需要真实审批账号，RESEARCH_03 继续未进入处理阶段。
- 因 Edge 扩展控制阻断，本轮未新增可归档的正式 UI 证据；此前已有 Edge 记录不能替代本轮修复后的复测。

## 本轮后续 Edge 复测（单实例）

- 唯一 API/Worker 链：Docker 依赖 healthy，`/api/v1/health` 返回 200；Provider 明确为开发环境 `mock`。
- 研究工作台新建会话：旧课程表单清空；实时任务按“已识别 → 已生成执行计划 → 能力编排 → 外部证据检索”顺序推进，无重复提交事件。
- 资料依据：修复前曾观察到护理、英语教育和哲学书籍与电子信息课程问题混在 4 条证据中；新增领域过滤后，研究任务在 Edge 中进入游客审批门禁，未绕过审批生成最终证据答案，随后通过页面停止，显示“任务已停止/未生成新结果”。过滤行为由单测覆盖，正式审批后 UI 复测仍待授权账号。
- 刷新/恢复：在修复前实时任务上，刷新后的异步恢复窗口短暂显示 0 条，等待渲染稳定后恢复为原 4 条卡片和 4 个唯一 DOI；新会话显示“本次没有可展示的资料依据”。
- 学生端：学习工作台可打开，输入与课程选择控件正常，资料区域显示“资料会在这里出现”。
- 教师端：反馈指标、课程材料质量、OCR 只读复核队列和错误模板复核入口可打开；游客态不显示学生个人信息。
- 研究工作台：会话列表、科研检索入口和任务详情可打开。
- 管理员：游客态正确停留在“管理员登录”，并提示当前账号没有管理员权限。
- 数据不足：Edge 显示“数据分析尚未执行”，明确要求研究设计、数据清单和授权信息，没有执行原始数据分析或伪造结论。
- 普通知识问答：任务完成为本地安全后备，页面明确提示主模型未完成并已切换后备；这不是 Mock 结果，未将其记为 Mock 通过。
- 长等待/停止：研究任务显示“模型响应较慢，仍会自动完成”和等待秒数；停止后显示“任务已停止/未生成新结果”。
- 复测结束后已停止唯一服务链，8000 无监听、无 API/Worker/pytest 残留。

## 本轮资料依据修复与 Edge 复测（2026-08-14）

### 新发现的根因

- 课程证据卡的 `source_ref` 指向正确的知识库 chunk，但原文查看器在带 `chunk` 时默认打开 24,000 字符窗口，跨越多个章节；因此打开 KCL 证据时会同时显示后续“商业电阻器”等无关内容。
- 相邻 chunk 存在重叠，旧上下文投影仅按完整字符串去重，无法识别同一文档内高包含率的重叠片段。

### 修复

- `apps/api/app/api/v1/knowledge.py`：带 chunk 的原文查看默认窗口收窄为 8,000 字符；无 chunk 的完整文档分页仍保持 24,000 字符默认值。
- `apps/api/app/services/retrieval_context.py`：对同一文档内高包含率检索片段去重，保留不同文档或不同主题章节的独立证据。
- `apps/api/tests/test_knowledge_api.py` 与 `test_knowledge_index_pipeline.py`：增加原文窗口边界和重叠证据回归测试。

### Edge 实际结果

- 唯一服务链 `/api/v1/health` 返回 200，database、Redis、MinIO 均为 `ok`，provider 为开发态 `mock`。
- KCL 课程问答完成并显示本地资料依据及后备模型提示；原文查看器修复后保持在 KCL/基尔霍夫定律附近，不再出现“商业电阻器”或功率章节。
- 同一会话刷新后任务和证据可恢复；新建会话后旧证据清空并显示“本次没有可展示的资料依据”。
- 科研检索完成后显示“当前主题暂无可核验证据”，没有伪造论文、DOI 或链接。
- 教师/研究者游客入口可打开统一工作台；管理员页面停留在管理员登录和权限提示；Edge 控制台未观察到错误日志。

### 本轮验证限制

- Edge 控制层在一次长任务最终 DOM 读取时超时并重置，因此未将该次最终卡片计数记为通过；已获得的原文错位修复、刷新恢复、新会话清理和空证据提示均来自可读页面状态。
- 上下文去重回归：`3 passed`；Ruff、Mypy、`node --check`、`git diff --check` 通过。
- 新增原文窗口单测在 60 秒限时内未返回，已精确清理 pytest，不能计为通过；全量 Web pytest 仍未完成。
- 最终停止服务后 8000 端口释放，未发现项目 API/Worker/pytest 残留。

## 验证限制

- 新增纯函数测试在显式加载 `pytest-cov` 后为 `1 passed`；统一出口回归测试及整文件测试在 120/150 秒限时内未返回，未计为通过。项目 `apps/api/pyproject.toml` 默认通过 `addopts` 注入覆盖率参数；禁用自动插件时需显式 `-p pytest_cov`，否则会因未知参数退出。
- 本轮没有真实审批账号，因此未完成“审批后恢复”以及审批门禁后正式证据卡片的 Edge 复测。
