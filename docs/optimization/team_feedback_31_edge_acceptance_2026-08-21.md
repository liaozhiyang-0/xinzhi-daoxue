# 组员反馈 31 场景 Edge 全流程验收记录

日期：2026-08-21；持续更新：2026-08-22
入口：`http://localhost:8000/workspace`，通过 Edge 可见页面操作
运行环境：Docker Compose；健康检查 `status=ok`；当前默认 `active_provider=local`，真实模型 Provider 已配置；`SOLVER_CT_v1.0_frozen`。

## 2026-08-22 真实模型优先增量记录

- 已将正常应用默认从 `mock` 调整为 `local`，并关闭静默 Mock fallback；确定性检查脚本仍显式使用 Mock，不计入真实验收。
- Edge `/system` 已真实核验：页面显示“真实模型已配置”，并列出 `dashscope`、`iflytek_spark`；Agent Runtime 与真实模型 Provider 不再混为一个状态。
- Edge 首次真实知识问答暴露 `local_runtime_handler_missing`（`LEARN_01_KNOWLEDGE_QA_V1`）；已补齐本地 Runtime 的主 Agent/别名注册。第二次重试进入“带提示完成”，页面明确显示未使用课程资料、证据不足和无独立质量判定。
- API 日志确认第二次运行窗口内存在 DashScope Chat Completions `HTTP 200`；因此本次是实际 Provider 调用，但由于课程资料不足，不能把该结果计作知识内容通过。
- 真实 RAG 健康核验发现文本模型 fallback 维度 `384` 与 Qdrant 现有集合 `512` 不一致；已增加维度兼容性健康字段和降级原因，后续必须先恢复匹配的真实 embedding 或执行可审计的版本化索引迁移，禁止直接删除现有集合。
- 镜像模型 `google/siglip2-base-patch16-224` 当前因本地缓存/网络不可用而未加载；G1-Q01～G1-Q09 仍不能计入真实视觉验收。
- Worker 更新后再次从 Edge 实测资料不足场景：页面显示“资料不足，待补充”，答案质量提示“本次未生成模型答案”，执行过程“结果检查/回答生成”均为 `partial`；该场景仍不是内容通过，但已满足失败优先和状态不误导门。
- 2026-08-22 后续真实 RAG 验证：API 正式进程已加载真实 `BAAI/bge-small-zh-v1.5`，512 维向量与 Qdrant 文本集合一致；AE“负反馈放大器稳定性”查询真实命中第八章教材，RAG 返回 `ready` 和可追溯 `retrieval_trace_id`。这只证明文本检索准入，不替代 Edge 场景验收。
- 2026-08-22 真实结构化恢复验证：DashScope `qwen3.5-flash` 课程分类调用在 16 token 上限下真实返回 `finish_reason=length`；同一路由恢复到 512 token 后成功得到完整 `course=AE` JSON，并保留恢复元数据。该验证未通过 Edge 页面提交，因此只计 Provider/Agent 准入，不计 31 场景 T2。
- 2026-08-22 Edge 复验阻塞：Edge 当前打开本地页面显示 `ERR_BLOCKED_BY_CLIENT`，随后 `/workspace` 恢复可用；浏览器扩展的文件选择器仍在 `filechooser` 事件处超时，因此图片上传未能在 Edge 页面完成。
- 2026-08-22 Edge 已恢复：从 `/workspace` 真实提交 AE“负反馈放大器稳定性与自激振荡”问题，页面显示 `带提示完成`、使用 3 条课程资料、Runtime 已完成；任务详情显示 `provider=dashscope`，结果含 `generation_model=qwen3.5-flash`、真实教材章节和 `S1/S2/S3`。由于 `rag_status=degraded`（仅视觉模型缺失）且答案质量“需要复核”，本条只计真实链路/证据展示通过，不计内容零缺口通过。
- 本次 Edge 任务还发现生成耗时显示 0 ms 与真实模型调用不一致；API/Worker 更新后重新从 Edge 复验，同题任务显示生成耗时 `6549 ms`，任务 API 同时记录 `provider_latency_ms/model_latency_ms=6549`、`model_calls=2`、`provider=dashscope`、`generation_model=qwen3.5-flash`、`mock_used=false`。该任务仍因 SigLIP 缺失为 `rag=degraded/evidence=partial`，不计为完整质量通过。
- 2026-08-22 真实视觉后端全流程复验：通过真实文件上传接口、队列/Worker、`ACADEMIC_PROBLEM_SOLVER` 和 DashScope `qwen3.7-plus` 回放 Q01 原图，任务 `task_7ce6687ee70c4d3fbb8eedc32d4989dd` 完成；`mock_used=false`、`vision_calls=1`、`structured_extraction=true`、`visual_structure_status=complete`、`can_continue=true`，输出卷积分段式及拐点说明。该记录不替代 Edge T2，因为扩展文件选择器未完成页面上传。
- 2026-08-22 真实视觉兼容修复：视觉调用启用 Provider JSON 模式，并归一化真实模型返回的信号字段别名；只对题干已明确的连续时间卷积关系和端点开闭提示做窄化放行，电路拓扑、关键参数和未知连接仍强制拒答。学术求解真实耗时/usage 指标也已补齐；Q01 的 `math_quality.publishable=false` 暴露 `\\in`、`\\Rightarrow` 仍需数学渲染器兼容。

> 2026-08-22 Q01 最新真实后端复验：任务 `task_1bf25313a69340149f54bc26726e9d02` 通过真实文件上传、Redis Worker、视觉 Agent 与求解 Agent；`mock_used=false`、DashScope `qwen3.7-plus`、`visual_structure_status=complete`、`can_continue=true`、真实生成完成，`math_quality.status=passed`、`publishable=true`、warnings 为空。真实输出驱动补齐了 `\\in`、`\\Rightarrow`、`\\implies`、`\\cap`。由于 Edge 文件选择器仍未通过，本条仍不计 Edge T2。

> 2026-08-22 视觉不确定性复验：同一真实信号图曾出现一次“空结构/不确定拓扑”结果，已增加题干完整信号事实的窄化放行；不会放宽电路图连接、极性和参数安全门。相关回归为 `58 passed`。

> 2026-08-22 Edge 控制通道后续复验：用户确认已允许文件 URL；重新绑定 Edge 后，通用 `/workspace` 的 DOM、文件选择器和真实 Q01 提交均成功。原先的控制通道超时不再是当前阻塞；新发现是带 `scenario_id=faculty_course_copilot_v1` 的 text-only 教师场景收到图片后会以 `mixed` 输入类型拒绝，说明入口场景绑定/输入合同存在问题。

> 2026-08-22 Provider 展示一致性复验：Q01 任务 `task_e4cf84d8fa914c5a978e7b5997a70962` 的 API 记录为 `provider=local_graph`（Runtime 适配通道），内部视觉/生成执行均为真实 `dashscope/qwen3.7-plus`。新增持久化生成溯源投影和前端静态资源版本号后，Edge“回答信息”正确显示 `实际 Provider=dashscope`、`Runtime 通道=local_graph`、`生成模型=qwen3.7-plus`；`mock_used=false`、`fallback_used=false`。质量仍为 `partial/needs_review`，不计内容零缺口通过。

> 2026-08-22 服务状态复核：Docker Compose 中 API 健康、Worker、Postgres、Redis、MinIO 均在运行；RAG `ready`，BGE 512 维、SigLIP 768 维，Qdrant 兼容且无维度不匹配。随后启用 Hugging Face 离线模式，Worker 重启后的 warmup 日志为 `status=ready failed=[]`，未再出现只读缓存 `.no_exist/processor_config.json` 写入警告；准生产仍需验证缓存版本/权限/挂载路径治理。

> 2026-08-22 缓存配置后真实 Runtime 回归：授权开发 E2E `solver_series_current` 任务 `task_b586ba73ab854cd48bcf806636f6e104` 完成，24 个事件严格递增，`mock_used=false`，底层模型为 DashScope `qwen3.6-flash`，模型调用 1 次、Provider latency 8078 ms；结果仍按 `partial/needs_review` 展示，因为独立确定性验证未触发。本条计真实 Worker/Provider 回归，不计 Edge T2。

> 2026-08-22 真实 Showcase Runtime 增量：`general_stack_explanation`（`GENERAL_QUESTION_V1`）和 `knowledge_capacitor_voltage`（`LEARN_01_LOCAL_RETRIEVAL_V1`）均完成，事件数分别为 23/20，严格有序且无 timeout/fallback；后者使用 DashScope 并生成 `retrieval_trace_id`，两份审计包均为 `mock_used=false`。通用问答仍标记 `local_agent` 且无独立模型名，未升级为真实模型内容通过。

> 2026-08-22 真实科研写作治理回归：初始真实任务发现无证据时仍显示 `accepted/publishable`；已补齐引用/事实复核门。容器重建后任务 `task_348749015f35403a8a815286ebf12e23` 显示 `evidence_status=insufficient`、`evidence_count=0`、`validation_status=warning`、`result_status=accepted_with_warnings`、`business_data.publishable=false`、`requires_review=true`，`mock_used=false`。本条计真实治理/Runtime 回归，不计 Edge T2。

> 2026-08-22 真实外部检索回归：`RESEARCH_01_ACADEMIC_SEARCH_V1` 任务 `task_5851a791781e4156acaf8c2ce2d6ae3a` 完成，27 个事件严格递增；外部检索真实完成并返回 6 条含 arXiv/DOI、URL、provider、摘要和审批状态的来源，`review_status=approved`、`evidence_status=sufficient`、`mock_used=false`。场景合同仍要求模型综合发布门，最终为 `accepted_with_warnings`、不可直接计科研内容完全通过；本条不是 Edge T2。

> 2026-08-22 真实教学/作业 Runtime 增量：备课任务 `task_9ba6360221a347a08d909b5216f42360` 与作业批改任务 `task_2c08800f1c7447d9bbe16bc749cbc9ac` 均完成，事件严格递增、无 fallback/timeout、`mock_used=false`，模型路由为 `qwen3.5-flash`；两者均保留 `completed_with_gaps`，继续阻断内容零缺口验收。

## 验收边界

- 31 个原始文本案例均从 Edge 工作台输入框逐项提交，覆盖前端输入、任务创建、路由、队列/Runtime、SSE 状态和结果展示；没有用后端接口替代 UI 提交。
- G1-Q01～G1-Q09 的原始案例带图片。Edge 文件 URL 权限现已允许；G1-Q01 已在通用 `/workspace` 成功完成图片选择、上传、真实视觉结构化和求解，但仍缺专用 `visual_acceptance.v1` 场景合同，因此只计真实 Edge/模型链路回归，不计图片组 T2。
- 历史记录中的本地回放曾使用 Mock；该结果只证明本地链路与降级契约，不等价于真实云端模型、真实视觉模型或真实外部 Provider 通过。当前正常默认已切换为 `local`，Mock 不计入真实验收。
- “等待人工审批”是持久检查点，不是失败；为继续后续案例，观察窗口结束后通过页面“停止”结束该本地测试任务。观察到完整结果且页面 `status: 已完成` 时，按完成记录，即使旧判定器未命中“任务已完成”标题。

## 逐案例最终可见结果

| 案例 | 预期意图 | Edge 可见路由/课程 | 终态与证据 | 备注 |
|---|---|---|---|---|
| G1-Q01 | solve_problem | 信号与系统 | 观察窗口内未完成，已停止 | 文本路径；未上传图片 |
| G1-Q02 | solve_problem | 信号与系统 | 观察窗口内未完成，已停止 | 文本路径；未上传图片 |
| G1-Q03 | solve_problem | 信号与系统 | 观察窗口内未完成，已停止 | 文本路径；未上传图片 |
| G1-Q04 | solve_problem | 电路理论 | 已出现求解正文，但 Runtime 仍运行，观察后停止 | 文本路径；未上传图片 |
| G1-Q05 | solve_problem | 电路理论 | 观察窗口内未完成，已停止 | 文本路径；未上传图片 |
| G1-Q06 | solve_problem | 模拟电子技术 | 页面 `status: 已完成`，展示工作点/小信号/饱和分析 | 文本路径；未上传图片 |
| G1-Q07 | solve_problem | 模拟电子技术 | 页面 `status: 已完成`，展示三运放/增益推导 | 修复后课程标签稳定 |
| G1-Q08 | solve_problem | 数字电子技术 | 页面 `status: 已完成` | 修复 R-2R/DAC 课程识别后复核 |
| G1-Q09 | solve_problem | 数字电子技术 | 一次回放完成；另一次观察窗口内未完成 | 文本路径；未上传图片 |
| G1-Q10 | lesson_prep | 信号与系统；专用教师备课路径 | 进入等待人工审批/模型响应检查点，观察后停止 | 不再静默降级为通用模型 |
| G1-Q11 | assignment_review | 信号与系统；作业批改与首错诊断 | 页面 `status: 已完成`，可见首错、错误传播、验证任务和教师复核 | 修复卷积课程预览后复核 |
| G1-Q12 | learning_advice | 信号与系统 | 观察窗口内未完成，已停止 | 仍需真实模型/证据生成能力 |
| G1-Q13 | academic_search | 科研任务 | 观察窗口内未完成，已停止 | 不作真实科研结论 |
| G1-Q14 | summarize_knowledge | 数字电子技术；学院治理 | 页面 `status: 已完成`，同时保留 `not_available` 能力状态 | 完成态不代表资产可发布 |
| G2-01 | academic_search | 科研任务 | 30 秒观察窗口内未完成，已停止 | 需真实检索链路和更长运行窗口 |
| G2-02 | lesson_prep | 模拟电子技术 | 等待人工审批，观察后停止 | 审批/模型生成未闭环 |
| G2-03 | lesson_prep | 信号与系统；教师智能备课 | 页面 `status: 已完成`，可见傅里叶频移推导、课堂互动、证据缺口和教师复核 | 公式/来源质量仍需真实模型验收 |
| G2-04 | explain_concept | 数字电子技术；知识问答 | 页面 `status: 已完成` | 需继续核对诊断任务是否应升级为求解 Agent |
| G2-05 | learning_advice | 模拟电子技术 | 课程标签修正为模拟电子技术；Runtime 观察窗口内未完成，已停止 | BJT/静态工作点边界已修正 |
| G2-06 | academic_search | 科研任务 | 页面 `status: 已完成`，展示科研检索结果/核心结论/关键发现 | 不等价于证据真实充分 |
| G2-07 | solve_problem | 模拟电子技术 | 观察窗口内未完成，已停止 | 公式 AST、单位和真实模型仍需验收 |
| G2-08 | lesson_prep | 数字电子技术 | 等待人工审批，观察后停止 | 审批/模型生成未闭环 |
| G2-09 | general_qa | 数字电子技术 | 课程标签修正为数字电子技术；Runtime 观察窗口内未完成，已停止 | FPGA/数字钟/CMOS 课程边界已修正 |
| G2-10 | assignment_review | 模拟电子技术；作业批改 | 页面 `status: 已完成` | 展示首错诊断路径 |
| G2-11 | assignment_review | 数字电子技术 | 等待人工审批，观察后停止 | 需区分审批等待与业务失败 |
| G2-12 | learning_advice | 模拟电子技术；学习路径 | 页面可见 `status: 已完成`、7 天计划、验证任务和教师介入节点 | 旧判定器曾误记 timeout，已按可见终态核对 |
| G2-13 | learning_advice | 电路理论 | 观察窗口内未完成，已停止 | 拉普拉斯/极点分布课程标签已修正 |
| G2-14 | academic_search | 科研任务 | 页面 `status: 已完成` | 不等价于真实文献证据通过 |
| G2-15 | academic_search | 科研任务 | 最终修正复核显示科研任务；观察窗口内未完成，已停止 | 不再显示通信原理或继承课程上下文 |
| G2-16 | solve_problem | 模拟电子技术；电路求解 | 页面 `status: 已完成`，展示工作状态、原因和验证步骤 | 未观察到科研标题串入 |
| G2-17 | solve_problem | 模拟电子技术；电路求解 | 页面 `status: 已完成`，展示漂移机制、补偿方案和自检清单 | 未观察到科研标题串入 |

## 本轮实际修正并重新加载的内容

- 课程强标记与 UI 预览同步：信号与系统、卷积、仪表放大器/三运放、R-2R/DAC、BJT/静态工作点、FPGA/数字钟/CMOS、Buck/Boost、拉普拉斯/极点分布。
- 教师备课与作业批改 Agent 的课程能力从 CT/AE/DE 扩展到 SS/DSP/COMM，避免明确课程识别后因能力门禁被静默转成通用模型。
- 研究请求的课程中性边界：检索、文献、科研等请求优先得到 UNKNOWN/科研上下文；“侧信道”不再被宽泛的“信道”误判为通信原理。
- 新增路由和 UI 回归断言，覆盖课程—意图—专用 Agent 三元关系及研究中性课程；未修改 `apps/api/app/agents/solver_ct`。

## 验证结果

- 路由/UI 定向回归：最终阶段 `11 passed, 92 deselected, 2 warnings`；另有课程修正阶段 `10 passed`、教师路由阶段 `6 passed`。
- Ruff：涉及 `router.py`、`task_router` 回归和工作台 UI 回归的检查通过。
- `git diff --check`：通过。
- `git diff --name-only -- apps/api/app/agents/solver_ct`：无输出，冻结基线未修改。
- Docker：当前 API/queue-worker 服务健康检查为 `status=ok`，数据库/Redis/MinIO 正常、`configuration_status=ready`、`active_provider=mock`；本轮重新构建因 Docker Hub EOF 未完成，定向验证使用现有容器并临时同步改动，不能视为完整镜像重建验收。
- 本轮 Runtime UI 定向修正：长等待提示现在读取 Runtime 控制状态；`waiting_review`/`waiting_approval` 显示“等待人工审批”，`waiting_user`/`waiting_input` 显示“等待补充信息”，不会再误报为模型响应慢。`node --check` 与 `git diff --check` 通过；宿主机/现有容器缺少 pytest/ruff，Docker 重建因 Docker Hub EOF 未完成。为进行 Edge 页面联调，已将前端文件临时同步到当前 `xzd-api` 容器，重建容器后需重新部署验证。
- 后续 Edge 复核又确认两个前端状态竞态并已修复：提交新任务时先归档旧回答、再初始化 pending 面板，避免面板被再次隐藏；停止任务时立即清空 Runtime 控制投影，避免“任务已停止”与“等待人工审批”并存。项目容器定向回归为 `61 passed, 2 deselected`，新增 UI 顺序/取消清理回归为 `4 passed`；Edge G2-02 实测显示“等待人工审批”及 checkpoint 说明，点击停止后仅保留“任务已停止/未生成新回答”，控制区消失。
- 本轮补充会话隔离：切换/新建会话时递增 Runtime 控制请求代际，旧会话的异步控制响应不会重新注入当前会话；新增会话回归 `5 passed`，Edge 新建会话后恢复为“等待提问”，未带入旧任务控制区。
- 本轮多模态边界修正：视觉契约包含波形/频谱区间时，不再强制套用电路器件端点拓扑校验；电路契约仍要求器件、连接、端点映射、极性和参考方向。新增 G1-Q01 信号图回归，视觉结构化结果通过时允许继续；视觉回归 `5 passed`，工作台定向回归 `6 passed`。
- 本轮上传链路修正：前端材料扩展名兜底补齐 jpg/jpeg/png/webp/tsv；后端仅对图片扩展名且 MIME 为 `application/octet-stream` 的上传执行图片签名识别，确认真实格式后归一为标准 MIME，不放宽其他文件类型。新增上传回归 `2 passed`。
- 真实图片接口链路：使用 `组员反馈/组员一反馈/images/Q01_signal_convolution.png` 实际上传成功，返回 `content_type=image/png`、`ingestion_status=ready`；随后创建 CT 解题任务并进入 `completed/local_graph`，Mock 视觉能力未形成结构化识别时按安全边界返回“不能仅凭视觉摘要计算”的拒答，未伪造答案。
- Edge 文件上传仍被扩展层 `Not allowed` 拦截；已确认阻塞点来自 Edge 扩展的本地文件访问权限，而非应用 `/api/v1/files`。故本轮不能把该案例记为 Edge 图片上传通过。
- 本轮补充输出质量回归：公式输出契约、历史质量投影、任务结果展示和 31 场景业务契约共 `71 passed`（其中组员反馈输出契约 `35 passed`、公式/历史/任务展示 `36 passed`）；此前容器缺少组员二 HTML 时产生的失败仅为测试输入文件缺失，补齐临时测试输入后全部通过。
- 本轮修正测试隔离：`tests/conftest.py` 在导入应用前清除外部模型/检索密钥，避免 Docker 开发环境变量让本地 Mock Runtime 误触发真实 Provider。修正后 G2-05、G2-07、G2-09、G2-12、G2-13 定向 Runtime 回放 `5 passed`，Provider 配置回归 `10 passed`；图片真实字节校验与多图准备 `2 passed`。
- 再次尝试 Edge Q01 原图上传，扩展仍返回 `Not allowed`；阻塞状态未改变，未将其误记为 Edge 图片验收通过。
- 本轮会话连续性修正：上下文组装改为按当前课程选取最新摘要，避免课程切换后被另一课程的较新摘要遮蔽；新增“CT 摘要较旧、AE 摘要较新时仍恢复 CT 摘要”的回归，`test_context_assembly.py` 与 `test_context_cache.py` 共 `14 passed, 2 warnings`。
- 本轮 Edge G2-02 定向复核：真实页面提交“模拟电子技术”45 分钟单管共射备课请求，页面正确显示课程为模拟电子技术并进入“等待人工审批”检查点；点击停止后仅显示“已停止/未生成新结果”，未残留等待审批控制区。该次仍为 Mock/本地 Runtime，不代表真实模型审批通过。
- 本轮 Runtime 文案修正：工作台 `provider_timeout` 降级映射存在重复对象键，后者会静默覆盖前者；现已保留单一稳定文案并新增静态回归，专项 UI 测试 `1 passed, 1 warning`。
- 本轮视觉能力预检修正：学术求解器原先只检查视觉路由主模型，主模型不可用时会跳过整段图片提取，即使备用视觉模型可用；现改用统一 `ModelService.preflight(..., modality="image")` 检查主/备用能力，视觉专项回归 `9 passed, 2 warnings`。
- 本轮 Edge 科研定向复核：提交宽禁带半导体近三年科研证据请求后，页面正确识别为“科研任务”，外部证据节点进入进行中；观察窗口内未形成结果时停止，页面显示“已停止/未生成新结果”，未把未审核候选展示为可发布结论。
- 本轮科研状态修正：外部候选因 `not_run/failed/rejected` 被清空后，场景契约仍保留审核状态，不再误报 `not_applicable`；科研输出与证据审核回归 `18 passed, 1 warning`。
- 本轮终态展示修正：通用 UI、执行链、学生结果和管理任务表不再把 `cancelled` 归类为“失败/未完成”；统一显示“已停止”，并使用独立的警示色终态。专项状态回归 `3 passed, 1 warning`，前端 `node --check`、Python 编译和冻结基线检查通过。

## 剩余问题与风险清单

1. **Provider 真实性未完成**：当前为 Mock；需要具备授权凭据、Flow ID 和已发布 Agent 后，分别执行真实模型、真实检索和真实 SSE/Runtime 验收。
2. **视觉输入 Edge 验收部分完成**：G1-Q01 已通过 Edge 文件选择、真实上传、视觉结构化和求解链路；仍需为 Q01～Q09 绑定专用视觉场景合同并完成图片预检、结构化拓扑、拒答条件、单位和公式链，不能因 Q01 通用工作台回放而关闭整组问题。
3. **教师/学习路径运行能力未闭环**：G1-Q10、G2-Q02、G2-Q08、G2-Q11 进入人工审批；G1-Q12、G2-Q01、G2-Q05、G2-Q07、G2-Q09、G2-Q13 等在本地观察窗口内未完成，需要区分排队、模型生成、审批、超时和真实失败。
4. **完成态与业务质量仍需分层**：G1-Q14 的 `not_available` 和学习路径的证据不足不能只显示为业务成功；应继续让 `publishable`、`requires_review`、证据完整性和 Runtime 终态在前后端一致呈现。
5. **数学渲染仍需真实结果回放**：需要对 G2-03/G2-07 的公式 AST、量纲、LaTeX/MathML/KaTeX、复制文本、SSE 重连和历史恢复做真实模型验收。
6. **科研证据质量仍需真实检索审计**：保留逐文献来源、日期、DOI/arXiv、失败 Provider、重试和证据缺口；Mock 检索结果不构成科研结论。
7. **跨会话/并发/恢复仍需扩大验收**：本轮证明页面未把 G2-16/G2-17 标题替换成前一科研标题，但不替代双 worker、共享数据库、断线恢复、并发会话和隐私日志审计。
8. **静态回归存在第三方弃用警告**：本轮测试仍有 Starlette/httpx 与 LangChain 相关警告，未作为业务失败处理，后续需单独治理资源生命周期和依赖升级。
9. **测试环境变量边界**：测试隔离已清除外部密钥，但宿主机/Compose 环境仍可能存在真实 Provider 配置；真实 Provider 验收必须使用显式授权命令和独立凭据，不能从普通回归环境继承。
10. **会话摘要选择已修正但需扩大验收**：当前课程摘要不会再被其他课程的更新摘要遮蔽；仍需在 Edge 中验证真实课程切换、断线恢复、摘要压缩和多会话并发下的连续性与隐私隔离。
11. **视觉能力预检已覆盖主/备用模型**：图片任务现在会识别备用视觉模型是否可用；仍需在真实 Provider 配置下验证主模型故障转备用、视觉超时、结构化拒答和 Runtime/SSE 终态的一致性。
12. **科研审核状态已覆盖空候选结果**：未审核候选被清空后仍显示 `not_run/failed/rejected` 并保持不可发布；仍需真实检索 Provider 回放来源完整性、时间窗、引用覆盖和人工放行后的恢复链路。

## 2026-08-22 Q01/Q02 真实 Edge 复验增量

- 已确认 Edge 文件 URL 权限可用，并通过 Edge 真实选择两张组员一图片：Q01 `Q01_signal_convolution.png`（SHA-256 `a250a31d6150d0438742ed37f889aaedd072ba1389134f292fff92d8052bc8645`）和 Q02 `Q02_signal_spectrum_modulation.png`（SHA-256 `3f53301f52fe1bb3489f4dc6dc14913b4493d135debe4d28cb4ef5904589d4fc`）。
- Q01 专用场景 `academic_visual_problem_solver_v1` 的真实任务 `task_b404f283dd674a0c9c9bde3a6675b4d1`：视觉验收通过、真实 `dashscope/qwen3.7-plus` 完成求解、数学质量通过、结构化字段无缺失；证据状态 partial 和人工复核策略使最终状态保持 `completed_with_gaps`，不可发布。
- Q02 专用场景 `academic_visual_spectrum_solver_v1` 的最新真实任务 `task_7ba07093d3e147f7b092b913ebfb7035`：视觉与求解均使用真实 `dashscope/qwen3.7-plus`，`visual_acceptance=passed`、`visual_topology_validated=true`、`model_execution=completed`、`math_quality=passed`、场景字段无缺失；仍因课程确认/人工复核策略为 `completed_with_gaps/publishable=false`。
- 真实回归暴露并修复了视觉门禁的深层误判：频谱题目已由文字明确支撑区间时，坐标轴刻度、箭头、正方向等非关键标注不应阻断求解；但频率轴和支撑区间等关键事实仍必须验收通过。另补充了真实输出中 `Lambda`、`cup` 的数学符号白名单。
- 当前计数：Q01/Q02 已有专用场景和真实 Edge 证据；G1-Q03～Q09、G1-Q10～Q14、组员二场景及可靠性/治理/准生产门禁仍未关闭。上述两条不能替代 31 场景全量 T2/T3。

## 2026-08-22 G2-16 专用场景真实回归

- 新增 `academic_text_diagnostic_solver_v1`，将 G2-16/G2-17 从无场景契约的课程/意图直路由纳入可审计案例选择；G2-16 使用 `scenario_case_id=g2-16-bjt-cutoff`。
- 真实任务 `task_2c0be8b54551426ea89970a7cee10127`：`mock_used=false`，实际 Provider/模型为 `dashscope/qwen3.6-flash`，模型执行完成；`present_fields` 覆盖 observation、工作区、原因、验证、安全边界和复核边界，`missing_fields` 为空。
- 结果仍为 `quality_gaps=manual_review`、`publishable=false`。这不是失败，而是实验安全诊断必须由人员确认；该结果不计“可发布通过”，但计入真实模型/场景契约/前后端状态一致性回归。
- G2-17 尚未完成真实 Provider 复测；组员二其余 15 条、Edge 页面 T2、科研证据、公式/历史/SSE、并发和准生产门禁仍未关闭。
- G2-17 真实任务 `task_55ae950ed6164f978d3c2f92daa2bf5d` 随后完成：`mock_used=false`，`dashscope/qwen3.6-flash` 完成，答案覆盖非理想诊断、补偿元件、验证步骤、安全边界和复核边界；保留 `quality_gaps=manual_review,math_rendering`、`publishable=false`。因此 G2-16/G2-17 已有真实 Provider/场景契约证据，但仍不是可发布通过。

## 2026-08-22 Q03 真实模型门控纠偏记录

- 通过真实图片上传、Redis Worker、`ACADEMIC_PROBLEM_SOLVER` 和 DashScope 回放 `bandpass-sampling`，任务 `task_127a3a3490a543518c7b39f073834641` 完成；`mock_used=false`，视觉阶段为 `dashscope/qwen3.7-plus`，实际调用 2 次（初次结构化提取 + 有界重试）。
- 模型未稳定返回 `positive_band/negative_band/band_edges`，所以 `visual_acceptance=blocked`、`visual_topology_validated=false`，该结果不计视觉验收通过。
- 题干本身明确写出 `[8,10] kHz` 和 `[-10,-8] kHz`，系统记录 `prompt_facts_cover=true`。此前视觉边界策略仍无条件按拓扑阻断，造成“可由用户提供事实继续求解”策略未落地；已修复为仅在该条件下跳过拓扑阻断，仍保留视觉门禁阻断和不可发布状态。
- 修复后真实求解阶段调用 `dashscope/qwen3.7-plus` 1 次并完成，结果含 `model_execution.status=completed`、`mock_used=false`；同时暴露 `math_rendering` 质量缺口，需继续完成公式 AST、单位、渲染和发布门禁。
- 本轮代码回归：相关 Ruff、Python 编译、场景/视觉契约测试 `49 passed`，前端 `workspace.js` 与 `ts/workspace-contracts.js` 语法检查通过；Docker 运行容器已同步并健康。Edge 扩展读取既有页面本轮再次超时，因此本条是后端真实全流程证据，不计 Edge 页面 T2。

## 2026-08-22 G2-10/G2-11 Edge 真实提交与 Provider 对账

- Edge 工作台加载 `assessment_diagnosis_v1` 的 `g2-10-bypass-capacitor` 案例并提交，真实任务 `task_5ec21ab6e3584aada03059841c01687b` 完成；API 显示 `TEACH_02_ASSIGNMENT_REVIEW_V1`、`mock_used=false`、真实 `dashscope/qwen3.5-flash`、场景字段无缺失。
- 该任务事件共 26 条，序号 1–26 严格递增，覆盖创建、路由、Runtime 节点、资料检索、结果产物和终态；因此 Edge 提交、队列/Runtime、SSE/事件和持久化链路已取得可审计证据。
- G2-10 与真实重测 G2-11（`task_9884cc13cf704ff88061cb9543d28907`）均保留 `completed_with_gaps/publishable=false`，不自动定分；G2-10 的概念纠正由模型 `teacher_feedback` 映射并带来源标记。
- Edge 提交后读取完整结果 DOM 的控制通道再次超时，归类为浏览器观测缺陷；本条不把 DOM 读取失败升级为业务失败，也不把 API 真实结果冒充为完整 Edge T2。后续仍需复验页面结果面板实际展示的 Provider、模型、字段缺口和复核边界。
