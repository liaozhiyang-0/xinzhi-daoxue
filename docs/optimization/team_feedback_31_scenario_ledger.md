# 组员反馈 31 个场景长期改造台账

> 状态基线：2026-08-21。本文把组员一、组员二的真实测试反馈转换为可追踪的验收台账。它记录的是“当前已有证据”和“仍需补齐的证据”，不把通用单元测试等同于 31 个原始场景已经真实通过。

> 2026-08-22 增量：应用默认已切换到 `local`，真实模型 Provider 配置健康；Edge 首次真实知识问答暴露并修复了本地 Runtime Agent 别名注册缺口，后续重试真实调用 DashScope 但因课程资料不足仅达到“证据不足/待复核”。RAG 曾暴露 384/512 维度不匹配，现已关闭 legacy fallback，原生 Transformers BGE 已加载为 512 维并通过真实 AE 教材检索；SigLIP2 真实视觉模型已加载为 768 维，RAG 健康状态恢复 `ready`。资料不足场景现已在 Edge 显示“资料不足，待补充”并将结果检查/回答生成标为 `partial`。另已用真实 DashScope 验证结构化输出截断恢复，并从 Edge 完成一次真实 AE 课程问答/证据回放；Q01 已通过真实上传接口、队列/Worker、视觉 Agent 和求解 Agent 的后端全流程回放（不计 Edge T2，因为扩展文件选择器仍阻塞），当前仍有 31 场景 T2/T3、Edge 图片上传、数学渲染兼容和发布门禁未完成。

> 2026-08-22 Q01 最新证据：真实任务 `task_1bf25313a69340149f54bc26726e9d02` 已完成，`mock_used=false`，视觉结构/真实生成均完成，`can_continue=true`，数学质量 `passed/publishable=true` 且无 warnings；仍只能记为“真实后端通过”，Edge T2 未完成。视觉模型偶发空结构的窄化文本事实放行已加入，电路拓扑安全门保持不变。

## 一、验收口径

> 2026-08-22 追加：Q01 数学白名单已补齐 KaTeX 支持的 `\\in` 与 `\\Rightarrow`，并在 API 容器内真实校验为 `valid`、无 warnings；历史任务不回写，需重新提交真实 Q01 确认 `publishable=true`。因此 G1-Q01 仍是“真实后端通过、Edge T2 与数学质量复验待完成”。

> 2026-08-22 运行环境追加：容器重建曾暴露模型缓存与镜像源码未持久化的问题，已改为 API/Worker 共享 `HF_MODEL_CACHE_HOST_PATH` 只读挂载并重建镜像；重建后 Worker 持续运行且真实 RAG warmup 为 `ready`。该修复解决当前本地重建漂移，但仍需纳入双 Worker、发布环境和缓存版本门禁。

| 状态 | 含义 |
| --- | --- |
| `回归覆盖` | 已有确定性规则、路由、Runtime 或输出契约测试直接证明对应能力；仍需用原始输入做场景回放。 |
| `部分覆盖` | 已有共享根因的防护或通用能力，但缺少该场景的专门规则、输入回放、证据质量或端到端证明。 |
| `待补回归` | 当前没有足够的确定性规则/路由/契约测试，不能把问题交给模型自由发挥。 |
| `未真实验收` | 尚未使用真实 Provider、真实外部检索或原始图片完成可审计回放；本轮仓库检查不改变这一状态。 |

证据等级按以下顺序递增：

1. 静态检查与单元测试；
2. 原始文本/图片 fixture 的 Provider-free 回放；
3. 配置完整的真实 Provider 联调；
4. SSE、重试、取消、重连、持久化和发布环境验收。

只有达到第 3、4 级，且输出、证据、路由和 Runtime 日志均可关联到场景 ID，才可将对应场景标记为“已验收”。

## 二、31 个场景矩阵

### 组员一：14 个场景

来源：`组员反馈/组员一反馈/01_题目清单.md`、`02_标准答案与评分锚点.md`、`03_题源与改编说明.md`；Q01–Q09 同目录下的原始题图。

| ID | 场景与原始问题 | 反馈暴露的主要问题 | 当前覆盖等级 | 已有证据 | 真实验收状态 | 余留风险与下一动作 |
| --- | --- | --- | --- | --- | --- | --- |
| G1-Q01 | 卷积图像题 | 图片结构读取、卷积滑窗/边界理解可能被自然语言答案替代 | `部分覆盖` | 已完成真实 Q01 后端回放：SigLIP2 健康、DashScope 视觉 JSON、结构化信号字段、`ACADEMIC_PROBLEM_SOLVER` 求解和真实任务审计；`test_universal_academic_solver.py`、`test_targeted_solver_optimization.py` | `真实后端通过；Edge T2 未完成` | 修复 Edge 文件选择器后从工作台上传原图；补数学渲染器 `\\in`/`\\Rightarrow`；再验收端点、分段式、波形和公式发布门。 |
| G1-Q02 | 傅里叶调制图像题 | 频移、频谱位置和图中标注容易被模型臆测 | `部分覆盖` | 视觉提取契约、数学格式化和通用 Solver 回归 | `未真实验收` | 增加频谱坐标/标注的结构化字段与单位一致性检查，再回放原图。 |
| G1-Q03 | 8–10 kHz 带通信号采样 | 把普通低通奈奎斯特条件误用于带通采样，理论最小值应约为 4 kHz | `回归覆盖` | `academic_review.py` 的带通采样首错规则；`test_targeted_solver_optimization.py::test_bandpass_review_rejects_lowpass_minimum` | `未真实验收` | 用原始题图和不同频带/单位变体回放；检查可行采样区间、保护带和边界条件。 |
| G1-Q04 | 戴维南等效最大功率图像题 | 端口、电阻和负载连接关系读取不稳，可能套用错误拓扑 | `部分覆盖` | 视觉拓扑提取、实体/关系安全门和通用电路 Solver 测试 | `未真实验收` | 增加等效端口、`R_L=R_th` 和功率表达式的结构化验收；原图缺失信息时拒绝给唯一数值。 |
| G1-Q05 | 含受控源的功率计算图像题 | 受控源开关量、端口功率方向和依赖源处理容易混淆 | `部分覆盖` | AE Validator 的局部冲突校验、视觉结构化提取 | `未真实验收` | 增加受控源功率符号/参考方向 fixture；要求给出端口约定、开路/短路或测试源依据。 |
| G1-Q06 | BJT 放大电路及工作区边界图像题 | 工作区、削顶边界与偏置条件未形成可靠的证据链 | `部分覆盖` | `AEValidator` 的 BJT 工作区冲突检查、视觉拓扑安全门 | `未真实验收` | 增加 Q 点、`V_BE/V_CE`、削顶方向和偏置变化的结构化断言；禁止仅凭单个电压结论定区。 |
| G1-Q07 | 仪表放大器图像题 | 三运放拓扑、增益电阻位置和共模/差模含义可能识别错误 | `部分覆盖` | 视觉提取契约和 Solver 通用回归 | `未真实验收` | 补齐三运放拓扑/增益公式的专门 fixture；核对输入端、参考端和共模范围。 |
| G1-Q08 | R–2R DAC 图像题 | 电阻梯形网络、开关状态和权重求和易出现拓扑串线 | `部分覆盖` | 视觉实体/关系提取和通用数值/单位检查 | `未真实验收` | 增加节点连通性、终端电阻、位权和满量程输出的确定性验收。 |
| G1-Q09 | 555 施密特触发器图像题 | 阈值、滞回方向和充放电路径可能被错误拼接 | `部分覆盖` | 视觉结构化提取、通用电路 Solver 回归 | `未真实验收` | 增加阈值比较器、反馈分压、滞回窗口和输出状态转移 fixture。 |
| G1-Q10 | 备课：80 分钟课、核心段 20 分钟 | 时长约束、教学流程和核心内容比例可能被忽略 | `回归覆盖` | `internal_agent_execution.py`、`lesson_prep_runtime.py`；`test_internal_agent_execution.py`、`test_lesson_prep_runtime.py` | `未真实验收` | 用原始课程输入回放；校验总时长、核心段时长、目标—活动—评价闭环和证据标注。 |
| G1-Q11 | 作业批改：定位 Q01 首个错误 | 可能跳过首错，直接重做整题或给总体分数 | `回归覆盖` | assignment formatter 的“学生答案 + 首错”契约；`test_internal_agent_execution.py`、`test_assignment_review_runtime.py` | `未真实验收` | 用 Q01 原始答案及多步答案回放；验证首错稳定、后续有效步骤保留、无答案时不臆判。 |
| G1-Q12 | 个性化学习路径与会话连续性 | 历史上下文、当前课程和学生画像可能串线或丢失 | `部分覆盖` | `test_agent_runtime_foundation.py` 的会话/归档恢复、`test_research_frontier.py` 的跨域记忆隔离 | `未真实验收` | 增加同一学生跨轮路径回放、并发会话隔离、恢复后不重复副作用和隐私字段审计。 |
| G1-Q13 | 学术研究：近期证据 | 时间范围、相关性、来源等级和证据不足提示不稳定 | `回归覆盖` | `academic_paper_review.py`、`research_frontier_service.py`；近期日期、主题过滤、证据状态测试 | `未真实验收` | 使用可复现的外部 evidence fixture 和真实检索双跑；检查“近三年/近 N 个月”、引用与结论逐条绑定。 |
| G1-Q14 | 治理：Q08 资产进入公共课程库 | 学生私有资产、课程公共资产和发布审批边界可能混淆 | `部分覆盖` | `test_knowledge_qa_service.py` 的发布治理拒绝、`test_course_asset_audit.py` | `未真实验收` | 补充资产来源、授权、审批、撤回、审计日志和跨课程可见性的端到端矩阵。 |

### 组员二：17 个场景

来源：`组员反馈/组员二反馈.html`。HTML 行号是当前文件中的定位锚点，后续若重新导出 HTML，应同时更新锚点。

| ID | 原始输入（摘要） | 反馈暴露的主要问题 | 当前覆盖等级 | 已有证据 | 真实验收状态 | 余留风险与下一动作 |
| --- | --- | --- | --- | --- | --- | --- |
| G2-01 | SiC/GaN 功率器件近三年进展与产业瓶颈（HTML 12–13） | 检索无直接证据却可能生成产业结论 | `部分覆盖` | 相对时间规划、日期过滤、证据不足状态和研究简报净化测试 | `未真实验收` | 绑定硬件器件关键词、年份、产业瓶颈子问题；无足够一手/高质量来源时输出缺口而非综述。 |
| G2-02 | 45 分钟 BJT 共射课：目标、流程、分层练习、核心复习（HTML 58–59） | 教学时长与差异化活动不一定满足硬约束 | `部分覆盖` | Lesson Runtime 时长检查、备课业务契约和本地 RAG 复用测试 | `未真实验收` | 补充 45 分钟、目标可测量性、分层任务和复习闭环的场景 fixture。 |
| G2-03 | 傅里叶变换性质课：来源与学生推导活动（HTML 183–184） | 课程内容可生成，但来源和活动证据可能缺失；公式降级可能与正文展示脱节 | `部分覆盖` | 备课结构化输出、检索空结果提示、课程证据边界测试；`math_quality.v1` 输出契约 | `未真实验收` | 将“公式—推导任务—课程来源—评价标准—数学渲染质量”设为同一输出契约，缺来源或公式不安全时明确待补。 |
| G2-04 | Vivado 分频器 Verilog 时序违例诊断及类似验证题（HTML 299–301） | Agent 未通过 Runtime 完成，失败信息与业务状态不一致 | `回归覆盖` | Runtime 失败终态、子节点错误码保留、取消与重规划测试；`test_research_analysis_runtime.py`、Runtime execution 测试 | `未真实验收` | 以真实/脱敏 Verilog fixture 验证时序约束、综合报告输入绑定、失败可恢复性和 SSE 终态。 |
| G2-05 | BJT 实验错误与两周个性化计划（HTML 302–304） | Agent 未通过 Runtime 完成；计划可能缺少复盘/导师介入条件 | `回归覆盖` | Edge 真实任务 `task_114f6e78ff6c49f0a8c8ed86b5f2b891`；真实 `dashscope/qwen3.5-flash`；14 天计划；20 条 SSE 序号 1–20；页面 Provider/模型与 API 一致；`mock_used=false` | `真实 Edge/API 链路完成；内容门禁未通过` | 页面显示资料 0/0、答案需要复核；BJT 课程资料不足，`evidence_status=insufficient`、`completed_with_gaps/publishable=false`；仍需补真实 BJT 资料和教师复核。 |
| G2-06 | 过去 12 个月多模态 LLM 复杂视觉理解文献（HTML 306–307） | 检索结果与主题无关，证据相关性失守 | `部分覆盖` | 主题一致性过滤、非学术来源治理、近期日期过滤、无支持结论净化 | `未真实验收` | 建立“multimodal + complex visual understanding + 12 months”检索 fixture；逐条核对标题、摘要、结论和时间。 |
| G2-07 | 运放闭环带宽边界、相位延迟、幅度失真和补偿（HTML 429–431） | Agent 未通过 Runtime；负反馈公式/带宽推理可能断链，非法或不完整公式可能被误当成最终结论 | `部分覆盖` | `academic_review.py` 的 `AF` 闭环公式首错规则、Runtime 失败终态测试；数学渲染安全降级与发布门 | `未真实验收` | 补充闭环带宽、相位裕度、补偿网络的结构化推理 fixture，并验证公式 AST/单位/渲染状态与超时重试审计一致。 |
| G2-08 | Mealy/Moore 翻转课堂：20 分钟课前、30 分钟讨论（HTML 432–433） | 输出可用但引用与课程材料不足 | `部分覆盖` | Lesson 输出契约、证据缺口提示和资料复用测试 | `真实 Edge/API 链路完成；内容门禁未通过` | 最终真实任务 `task_de41531d7f8a4ea2a51888642d8d721d` 使用 DashScope `qwen3.5-flash`、`mock=false`、`fallback=false`，`generation_complete=true`；30 条事件序号严格递增。真实模型草稿已生成，但课时约束仍有警告、课程证据为 `insufficient`，需教师确认，不能发布。 |
| G2-09 | FPGA 多功能数字钟评分标准：4 维度、4 等级（HTML 542–543） | 评分标准生成被误路由为作业批改 | `回归覆盖` | 意图识别/路由回归、`general_question_service.py` 的 rubric 生成契约；`test_intent_recognition.py`、`test_general_question_service.py` | `未真实验收` | 用原始请求验证路由、四维度四等级、课程标准缺失时的待确认标记，以及不产生学生得分。 |
| G2-10 | 发射极旁路电容降低输入电阻并提高增益的首错判断（HTML 607–608） | 首错规则未覆盖“旁路电容、输入电阻、增益”的因果关系 | `回归覆盖` | 最终 Edge 真实任务 `task_3f3f12c43b4348c08982e40f57214790`；真实 `dashscope/qwen3.5-flash`；26 条 SSE 序号 1–26；页面/API Provider、Runtime、模型一致 | `真实 Edge/API 链路完成；语义门禁已生效` | `evidence_status=partial`、`completed_with_gaps/publishable=false`；`validation_status=warning`、`semantic_consistency=needs_review`，页面已展示具体矛盾原因；仍需教师核对频率、信号源内阻和输入电阻定义。 |
| G2-11 | CMOS 功耗：静态/动态构成与频率关系（HTML 661–662） | 把总功耗视为与频率无关，未区分静态与动态功耗 | `回归覆盖` | Edge 真实任务 `task_7d94ed54f7884238b275aefbcdc81656`；真实 `dashscope/qwen3.5-flash`；26 条 SSE 序号 1–26；结构化字段与页面结果已对账 | `真实 Edge/API 链路完成；教师复核未完成` | `evidence_status=partial`、`completed_with_gaps/publishable=false`；模型区分静态/动态功耗并生成频率对比验证题，仍需核对教材公式、参数和漏电边界。 |
| G2-12 | 四周全国电子设计竞赛电源计划：Buck/Boost、环路、EMI、实验（HTML 770–771） | 输出可用但来源、实验闭环和安全边界不足 | `回归覆盖` | Edge 真实任务 `task_90d0b0810bc340529de6822cd77f4ce4`；真实 `dashscope/qwen3.5-flash`；4 个周阶段按 28 天周期验收；20 条 SSE 序号 1–20 | `真实 Edge/API 链路完成；教师复核未完成` | `evidence_status=sufficient` 但 `quality_gaps=manual_review_required`、`publishable=false`；仍需教师确认电源安全、实验条件和课程边界。 |
| G2-13 | 拉普拉斯数学到物理稳定性/极点/响应的补救路径（HTML 875–876） | 数学结论与物理直觉、练习和证据连接不充分 | `回归覆盖` | 最终 Edge 真实任务 `task_60dbbc1f5d0a4342923d342badf2d991`；真实 `dashscope/qwen3.5-flash`；学习路径字段、主题证据门和页面展示均已回放 | `真实 Edge/API 链路完成；内容门禁未通过` | `evidence_status=insufficient`、`source_refs=[]`、`quality_gaps=manual_review_required`、`publishable=false`；已阻止无关课程片段冒充拉普拉斯证据，仍需补真实教材证据、前后测绑定和教师复核。 |
| G2-14 | 过去 18 个月边缘 YOLO 剪枝/量化（HTML 1031–1032） | 近期检索、任务边界和证据摘要可能失配 | `部分覆盖` | 相对月份窗口、主题过滤和证据净化测试 | `未真实验收` | 固化视觉模型/边缘部署/剪枝/量化/18 个月的查询与排除词，要求每项开销/精度结论有来源。 |
| G2-15 | 近期 RISC-V 侧信道硬件防御与面积/功耗开销（HTML 1149–1150） | 证据不足时输出空泛或不相关结论 | `部分覆盖` | 证据不足状态、时间窗过滤和研究前沿净化 | `未真实验收` | 将 RISC-V、side-channel、hardware defense、area/power overhead 设为联合约束；按防御策略逐条记录开销证据。 |
| G2-16 | 纯文本 BJT：`V_C≈V_CC` 且顶部削峰，判断工作状态、原因与验证（HTML 1195–1196） | 纯文本电路诊断被错误送入科研检索，未做电子学域路由 | `回归覆盖` | Edge 真实任务 `task_9ad6b7419845418a93b614ec3ca2fe30`；真实 `ACADEMIC_PROBLEM_SOLVER`、DashScope `qwen3.6-flash`；24 条 SSE 序号 1–24；场景字段齐全 | `真实 Edge/API 链路完成；确定性质量门部分通过` | 已正确路由并输出工作区、候选原因、逐项验证和安全边界；`quality_gate=partial`、`publishable=false`，仍需补确定性工作区/小信号/反馈规则证据。 |
| G2-17 | 运放积分器 `v_i=0` 但输出漂向负电源，诊断非理想原因并加元件（HTML 1241–1242） | 纯文本模拟电路故障被错误送入科研检索，非理想积分器知识未形成安全诊断 | `回归覆盖` | 最终 Edge 真实任务 `task_73f7739165af4cb083c16c692ce7e42f`；真实 `ACADEMIC_PROBLEM_SOLVER`、DashScope `qwen3.6-flash`；24 条 SSE 序号 1–24；全部场景字段和数学结果已对账 | `真实 Edge/API 链路完成；人工复核未完成` | `math_quality=passed`、`missing_fields=[]`，`quality_gaps=manual_review,manual_review_required`、`publishable=false`；已修复真实模型短语恢复，仍需数据手册、参数和实验条件复核。 |

## 三、共性根因与改造顺序

### P0：先保证“不会假成功”

1. Runtime 统一失败终态、取消终态、错误码和最具体失败节点；失败不得被包装成成功、空答案或普通“未配置”。
2. 任务创建继续保持非阻塞；Provider 只在执行节点调用，重试/恢复必须有稳定 execution key 和幂等边界。
3. 对真实 Provider、外部检索和图片输入增加 capability preflight；能力不满足时明确降级、等待输入或失败，不让模型自行猜测。
4. 建立场景 ID → request ID → runtime run ID → evidence ID → output contract 的全链路审计关联。

### P1：修复“路由对了但证据/输入不对”

1. 统一意图分层：学术求解、作业首错、评分标准生成、备课、个性化路径、科研前沿、纯文本电路诊断不能仅靠关键词互相兜底。
2. 统一上下文边界：会话、课程、学生、任务类型和历史证据必须显式绑定；跨域证据不得静默复用。
3. 研究输出使用“检索范围—候选证据—来源等级—时间窗—逐条引用—证据状态”的契约；证据不足时禁止生成代表性结论。
4. 备课/学习计划输出使用“目标—活动—时间—材料—评价—个性化触发条件”契约；缺课程材料时标记待确认。

### P1：补齐四类确定性学科规则

1. 多模态电路：拓扑、节点、端点、极性、单位、状态变量先结构化，再允许求解；不完整图像不得输出唯一数值。
2. 首错批改：补充旁路电容、CMOS 功耗、BJT 削峰、积分器漂移等规则；规则必须返回首错位置、原因、修正和验证步骤。
3. 数学/信号：继续扩展带通采样、频域变换、稳定性和单位规则，采用公式 AST 或受限解析，避免只依赖字符串匹配。
4. 输出契约：自然语言展示、结构化结果、证据和警告分离；禁止重复序列化 JSON、伪造引用、用 mock 结果冒充真实结果。

### P2：真实验收与发布门禁

1. 为 31 个场景建立脱敏文本/图片 fixture，固定输入哈希、期望路由、最低证据、首错/结构化字段和允许的降级状态。
2. 在配置完整且已发布的 Agent 上逐项做真实 Provider 联调；记录 provider、model、flow ID、耗时、重试、SSE 顺序和最终状态。
3. 对 Runtime 失败、取消、断线重连、恢复、人工审批和幂等副作用做成对测试；不得只验证最终文本。
4. 发布前运行 Ruff、Mypy、Pytest、配置/敏感文件检查、OpenAPI 导出、Docker Compose 配置检查；Docker 未实际运行时单独标记。
5. 每次回放更新本台账的“证据等级、运行批次、失败原因、修复提交/文件、剩余风险”，禁止只写“已修复”。

## 四、当前未闭环清单

截至本台账创建时，以下事项仍不能宣称完成：

- 31 个原始场景尚未全部完成端到端可审计回放；其中组员二 17 个原始 HTML 提问现已完成 Provider-free 路由与 Runtime 回放（14 个完成、G2-05/G2-12/G2-13 因模型能力未配置而明确失败），并已验证这三类任务在创建阶段记录 `generation_required/generation_available` 后进入明确失败终态；组员一 9 张原始题图已完成字节完整性与输入预处理回放；
- 已建立 31 条脱敏/压缩后的场景 fixture；G1-Q01–Q09 已绑定原始图片路径、SHA-256、文件大小和尺寸，但仍未完成视觉模型语义提取的逐题验收；
- 尚未完成真实 Provider 联调、真实外部检索验收和生产/准生产部署验证；
- G2-10、G2-11、G2-16、G2-17 已补确定性规则/领域路由回归，并完成组员二原始 HTML 提问的路由回放，但尚未完成真实 Provider 和端到端 Runtime 验收；
- G1-Q01–Q09 尚未完成图片级拓扑、坐标、极性、单位和公式链的模型输出逐题核验；代码端现已增加低置信度、不确定项、显式端点映射、端点映射一致性、源类器件极性/参考方向、重复标号和断开拓扑拒答门，并接入可选的 `visual_acceptance.v1` 场景级 `must_capture/refuse_if_missing` 契约；当前 fixture 仍主要证明原图完整性与视觉输入预处理链可用，尚未证明真实视觉模型逐题满足这些字段；
- 研究类场景虽已有时间窗、相关性、空证据拒绝和外部审核状态发布门禁，但尚未证明对 SiC/GaN、视觉理解、YOLO、RISC-V 侧信道等主题在真实 Provider 上稳定召回；
- 课程与学习计划类场景的材料来源、授权范围、个性化触发条件和跨会话恢复仍需端到端验收；
- 场景合同现在会跟随明确的活动课程；`AUTO/UNKNOWN` 仍只能使用演示课程作为回退，后续需要在请求缺少课程时增加课程识别或人工确认，避免把默认课程当成事实；
- 已增加 `task_audit.v1` 审计信封：任务输入保存输入/附件哈希、request/session/scenario/route/run_batch 信息；Runtime run 保存同一审计信息并回写 `runtime_run_id`；成功终态合并 Runtime 节点的 evidence/artifact ID 与输出合同版本，失败/取消终态保留失败分类。当前批次又补齐了直接取消和 Provider 取消分支的 `error_message/failure_category/heartbeat/lease/execution_owner` 与取消审计回写，并为成功、失败、取消增加终态互斥保护；仍需在真实场景回放中补齐证据包、最终展示版本和真实发布授权链；
- 授权 E2E 证据打包此前只把 `question` 写入配对输入快照，可能遗漏附件、数据集清单和研究请求，导致 Legacy/Runtime 输入被错误判定为相同；当前已改为稳定语义输入快照，保留内容字段与校验和，去除每次上传的文件 ID/存储键并规范化数据集来源引用；仍需在真实回放中与 `task_audit.v1` 的输入/附件哈希、最终展示合同逐项对账；
- 当前又补上这条对账链：`task_audit.v1` 增加 Runtime 请求内容哈希；打包器校验任务 ID、Agent、输入哈希、附件哈希、Runtime 请求哈希、终态和 Runtime run ID，并要求已完成任务存在完整最终展示对象；生成 structural suite 时只使用去除 `input_content` 的结构化副本，语义包保留受控输出、展示对象和脱敏审计投影。哈希或展示契约不一致时拒绝生成证据包；
- `AUTO/UNKNOWN` 课程歧义已增加显式状态：场景合同记录 `course_resolution`、来源和 `course_confirmation_required`；无明确课程时演示课程只作为待确认回退，合同进入 `completed_with_gaps` 且不可发布；路由识别出唯一课程时，在任务持久化前更新为 `router_detected`，避免继续使用演示课程过滤证据；仍需真实会话中验收人工确认交互和课程切换恢复。
- 会话摘要跨课程串线已修复：摘要仓库支持按 `structured_state.course_id` 选择同课程摘要；摘要压缩只读取当前课程消息，并用当前课程首条消息更新覆盖起点，不再把全局最新的旧课程摘要/来源 ID带入新课程摘要；仍需真实多进程并发和恢复回放验证数据库锁/重试行为。
- 课程资料撤回链已补强：已发布资料被拒绝或主动撤回时，课程资料状态进入 `withdrawn`、索引缓存标记为非活动，RAG 记录撤回资料/分块状态并过滤旧候选、图片子块和结果缓存版本；全量索引重建按活动 ID 清理旧向量，同时保留尚未重新发布资料的撤回状态。仍需真实 Qdrant、多进程索引和发布—撤回—重新发布端到端验收。
- 执行调试隐私边界已补强：管理员调试投影对原始输入、学生作答、附件/证据正文，以及由请求派生的 Runtime `goal`、解题目标、问题/会话摘要和任务事件中的 `user_prompt/raw_input/detail` 统一脱敏；新增回归覆盖原始字符串在完整 JSON 投影中不得回显。仍需继续审计错误事件、日志留存、提示词快照、角色范围和数据导出链，避免通过未命名字段或派生结果绕过脱敏。
- 运维观测访问边界已补强：`/api/v1/observability/{summary,metrics}` 和根 `/metrics` 统一复用 `require_admin`；认证关闭的本地开发保持可用，认证开启时匿名和学生均被拒绝，避免 Provider、模型、课程和队列聚合信息公开。仍需在真实部署中验证 Prometheus/反向代理凭据配置和最小权限运维角色。
- 调试题库资产旁路已补强：`/debug-assets/question-bank/analog-opamp.jpg` 现在复用 `require_admin`，认证开启时匿名和学生不能直接读取本地题库图片；仍需清点其他静态题库/课程资源路由，并在真实发布环境验证撤回后的缓存与 CDN 失效。
- 调试页面旁路已补强：`/debug`、`/debug/rag`、`/debug/agents`、`/debug/execution`、`/system` 和 `/demo` 页面统一要求管理员身份；认证开启时匿名/学生不能先取得内部页面再探测调试 API，学生端 `/student`、`/workspace` 保持独立。仍需真实反向代理、缓存和生产部署验收。
- 原始课程资料读取边界已补强：`/api/v1/knowledge/images/*`、`documents/*` 和 `document-pages/*` 在认证开启时要求已认证身份，并返回私有、不可缓存响应；路径解析仍保留课程根目录、扩展名和遍历校验。学生认证后可继续读取课程证据，匿名不能直接抓取原始资料；仍需把数据库中的发布/撤回状态与静态知识根目录逐项绑定，并验证 CDN/浏览器缓存清理。
- 上传课程资料证据链已补齐：`kb-material://课程/文件ID#chunk-N` 现在由发布状态约束的 `materials/*`、`material-pages/*` 接口解析，前端证据卡片可打开已发布上传资料；发布会清除旧撤回标记，审核拒绝和主动撤回都会失效索引并使接口返回 404，任务读取和聊天结果的历史证据投影会移除撤回来源并标记 `needs_review`。仍需真实认证会话验证旧任务、缓存、重新发布版本和多进程索引状态的一致性；答案正文仍保留为历史记录，不能被误当作重新生成的当前结论。
- 撤回资料的结果读取边界继续收紧：任务创建/取消/暂停/恢复/审批/输入/重协调等 `TaskRead` 响应、会话任务历史、聊天结果和执行调试投影统一经过撤回净化；`workflow_context.retrieved_context`、内部证据项、证据包、来源列表和展示摘要在发现撤回来源后清空或降级，索引状态文件不可读时对 `kb-material` 采取拒绝优先。RAG 稀疏候选现在也按 `source_ref` 识别上传资料，避免缺少 `material_file_id` 的旧候选绕过撤回过滤。
- 会话消息与上下文继续收口：助手消息元数据记录上传资料来源，`/sessions/{id}/messages`、会话摘要读取和 Runtime 上下文装配会识别撤回来源；撤回消息/摘要不会继续进入后续提示词，旧摘要或消息投影会标记需复核。上下文缓存键新增资料发布状态版本，撤回—重新发布不会复用撤回前缓存；旧摘要会回溯 `source_message_ids` 的消息元数据，缺少可追踪来源或来源已撤回时安全忽略。仍需真实 Redis 多进程、跨设备会话恢复和发布状态联调验收。
- 既有全量门禁曾记录 `14 warnings`：包括上游 LangGraph 弃用提示、SQLite/YAML 资源未关闭提示，以及一次 `aiosqlite` 工作线程在事件循环关闭后的未处理异常。本轮已针对本地根因做定向回归：Qdrant 本地 SQLite 探测连接不再泄漏，生产模式 deferred startup 在 SQLite 连接建立期间被取消时也能等待内部收尾；应用停机统一通过 RAG 服务的既有 `close()` 释放向量库、线程池和 Provider；执行调试测试改用 TestClient 生命周期内的 portal，纯异步学术写作测试改由 pytest 管理事件循环。变更前的完整门禁为 `1696 passed, 15 skipped, 11 warnings`，未再出现 aiosqlite 工作线程未处理异常或 Qdrant 本地探测连接告警；当前仍需继续定位 10 条原始 SQLite 连接警告及上游弃用提示，不能把资源生命周期标记为完全闭环；
- `SOLVER_CT v1.0` 冻结基线不得为覆盖反馈而直接修改；任何兼容性方案必须走现有 Provider/环境变量/HTTP 调用链并保留对照证据。

## 五、本轮验证记录（2026-08-21）

此前阶段曾完成一次 Provider-free 全量门禁；本轮为避免重复耗时全量测试，只对新增共享修复执行增量静态检查和定向回归。此前全量结果保留为历史基线，不能视为覆盖本轮新增代码。

本轮增量验证结果如下：

- 输出治理、直接取消、运行控制：Ruff 通过；`test_agent_result_governance.py`、`test_task_cancel.py`、`test_runtime_controls.py` 共 `20 passed, 2 warnings`；覆盖求解器独立最终答案、课程必需结构不可用状态、作业首错字段、证据不足初稿、取消终态元数据。
- Runtime/上下文/终态边界：此前定向回归中 `test_runtime_request_preparation.py` + `test_context_assembly.py` 为 `8 passed, 2 warnings`；Runtime 执行、终态、准备和上下文组合回归为 `28 passed, 2 warnings`；覆盖路由重评后重新编译意图计划、跨课程历史消息隔离、无效结果不得进入研究摄取、终态互写保护。
- 多模态结构化 Solver/内部视觉 Agent/31场景矩阵：`118 passed, 2 warnings`；覆盖端点映射字段、低置信度/不确定项/重复标号/断开拓扑拒答，以及 `can_continue=false` 的边界阻断。
- 证据治理、输出合同和外部研究 Runtime：`24 passed, 2 warnings`；覆盖引用必需但无来源、外部证据未完成审核、科研合同不可发布和既有外部检索运行链。
- SSE/Runtime 事件与终态边界：`19 passed, 2 warnings`；覆盖 `Last-Event-ID` 重连只重放游标之后的事件。
- 本轮未重新执行全量 Pytest、OpenAPI 导出、Docker Compose 运行验收；Ruff（`apps/api`）通过，Mypy `322` 个源文件无类型错误，`git diff --check` 通过；下次统一门禁必须覆盖本轮所有新增代码。
- 授权 E2E 输入快照与证据打包定向回归：`test_runtime_authorized_e2e_input.py` + `test_runtime_e2e_evidence_packager.py` 为 `7 passed`；Ruff 通过。该次运行同时暴露 `.venv` 的 coverage SQLite `ResourceWarning`，警告来自覆盖率插件连接而非应用连接，仍需在统一门禁中与应用 SQLite 警告分层确认。
- 本轮证据绑定回归：`test_task_audit.py`、`test_runtime_authorized_e2e_input.py`、`test_runtime_e2e_evidence_packager.py` 共 `12 passed, 2 warnings`；覆盖 Runtime 请求哈希、任务审计输入篡改拒绝、最终展示缺失门禁、结构化 suite 脱敏和 Runtime run ID 对账；Ruff、相关脚本 Mypy 和 `git diff --check` 通过。
- 非空 Runtime 请求补充回归：上述证据链范围扩展为 `13 passed, 2 warnings`；新增带 `research_question/data_manifest` 的配对样例，确认公开任务投影裁剪请求正文时，仍可依靠 `runtime_request_sha256` 与稳定语义快照完成对账。
- 课程歧义/场景合同/31场景矩阵定向回归：`89 passed, 2 warnings`；覆盖显式课程、演示课程回退、路由检测课程覆盖、不可发布合同和既有31场景路由/合同行为；Ruff、相关服务 Mypy 和 `git diff --check` 通过。
- 会话连续性定向回归：`test_context_assembly.py` + `test_task_session_commit.py` 为 `5 passed, 2 warnings`；覆盖旧课程摘要不进入当前课程压缩、来源消息与覆盖序列隔离、既有终态会话提交幂等；Ruff、相关服务 Mypy 和 `git diff --check` 通过。
- 外部证据审批边界增量回归：`test_external_research_runtime.py` + `test_runtime_scenario_policy.py` 为 `13 passed, 2 warnings`；覆盖降级/拒绝/未运行审核、审核计数不一致时回答前阻断、审批恢复后放行，以及 `_with_retrieval` 旁路二次清空未审核候选；Ruff、外部 Runtime Mypy 通过。
- 课程资料撤回与 RAG 失效回归：课程资料生命周期、撤回状态、旧向量/图片过滤、索引缓存版本和增量索引范围为 `5 passed, 2 warnings`；覆盖已发布资料被拒绝后撤回、manifest 排除、RAG 候选拒绝和全量重建清理路径；Ruff、相关服务 Mypy 通过。
- 执行调试隐私回归：`test_execution_debug_api.py` 为 `5 passed, 2 warnings`；覆盖管理员投影既有敏感键脱敏、Runtime handoff/checkpoint 可观测性，以及原始学生输入不从 `raw_input`、Runtime goal、问题摘要、持久化任务事件和 Runtime 派生观测字段回显；Ruff、相关接口 Mypy 通过。
- 运维观测认证回归：认证模块 `7 passed, 2 warnings`；覆盖既有认证/访客/调试访问控制，以及 API 观测摘要、API 文本指标和根 `/metrics` 的匿名/学生拒绝路径；Ruff、相关接口 Mypy 通过。
- 资产旁路认证回归：认证定向测试 `2 passed, 2 warnings`；覆盖题库图片路由与观测面在认证开启时的匿名/学生拒绝路径；Ruff、HTTP 应用 Mypy 通过。
- 调试页面认证回归：页面与题库资源定向测试 `2 passed, 2 warnings`；覆盖六个内部页面及题库图片路由的匿名/学生拒绝，以及开发态既有调试页契约未被破坏；Ruff、HTTP 应用 Mypy 通过。
- 原始课程资料身份与缓存回归：认证与知识 API 定向测试 `2 passed, 2 warnings`；覆盖图片、全文和分页资料接口的匿名拒绝、认证学生的资源不存在边界、三类响应的 `private/no-store` 头，以及既有开发态安全资源/数学规范化行为；Ruff、知识接口 Mypy 通过。
- 上传课程资料原文与撤回投影回归：课程资料、任务 API、任务展示和前端契约定向测试合计 `9 passed, 2 warnings`；覆盖发布上传资料的 `kb-material` 全文/分页读取、发布时清除撤回标记、撤回后的 404、历史结果证据卡片/引用/证据包过滤，以及前端材料 URI 路由；相关 Ruff、知识/任务/编排 Mypy 通过。
- 撤回结果全入口与 RAG 稀疏候选回归：任务历史/聊天、课程资料投影、调试投影和 RAG source URI 过滤专项测试 `4 passed, 2 warnings`；覆盖 `workflow_context` 正文清除、展示状态降级、任务/会话/聊天读取入口和缺少向量元数据时的 `kb-material` 撤回；相关 Ruff、5 个源文件 Mypy 通过。
- 会话消息/摘要/上下文撤回回归：任务历史专项 1 条、上下文装配 1 条、执行调试 1 条、RAG 稀疏候选 1 条最终均通过（分批执行，合计 `4 passed`，每批保留上游 `2 warnings`）；覆盖消息与摘要来源标记、撤回任务历史不再作为当前依据、上下文对撤回来源拒绝、执行调试投影净化、缺少向量元数据时按 `source_ref` 撤回，以及既有跨课程摘要隔离；Ruff、8 个源文件 Mypy 通过。期间发现并修复会话任务历史未读取净化结果的跨投影遗漏。
- 会话缓存与遗留摘要增量回归：5 个独立场景分批通过；覆盖资料撤回—重新发布生成不同状态版本、摘要从助手消息补齐资料来源、无来源旧摘要在撤回来源存在时不进入上下文、会话摘要 API 过滤回溯来源，以及既有跨课程摘要压缩；Ruff、6 个源文件 Mypy 通过。另补充 Redis 客户端在未知连接状态下执行会话失效的回归，避免清理进程跳过共享缓存扫描。
- 科研证据会话连续性边界增量回归：`SessionContextService` 现在只在同一科研 Agent 的明确科研请求/追问中暴露上一轮外部证据；普通任务和电路诊断不再接收研究证据，未审核或计数不完整的候选在会话落库与恢复时清空。上下文定向回归 `11 passed, 2 warnings`，意图与外部研究 Runtime 回归 `34 passed, 2 warnings`；仍需真实多进程会话恢复验证审核状态、检索批次和来源快照不被重写。
- 科研证据新检索隔离增量回归：修复显式新学术检索仍携带上一轮已审核 `previous_external_retrieval` 的串线；现在只有 `is_academic_search_follow_up()` 判定为同链路追问时才复用证据，新主题/新检索从空证据开始。上下文、缓存和外部研究定向回归 `25 passed, 2 warnings`；仍需真实多进程恢复验证审核信封、检索批次和来源快照不被重写。
- 共享缓存清理回归：`test_context_cache.py` 与任务历史/摘要专项合并执行 `6 passed, 2 warnings`；覆盖未知 Redis 连接状态下仍主动扫描并清除会话键，及撤回任务历史、遗留摘要、会话摘要 API 的当前净化契约。
- 真实共享缓存验收：使用随机隔离键启动 3 个独立 Python 进程，第一进程写入、第二进程从 Redis 恢复、第三进程执行会话失效并确认第一进程不可读；结果为 `write=redis/read=redis/invalidate=True`。本机 `docker compose config --quiet` 及 server 覆盖配置校验均通过；尚未启动完整 Docker 服务或完成双 API worker 的真实会话回放。
- 本机准生产依赖健康检查：运行中的 `xzd-postgres`、`xzd-redis`、`xzd-minio`、`xzd-qdrant`、`xzd-api` 和 `xzd-queue-worker` 均在 Docker 中，`GET /health` 返回 database/redis/minio `ok`；当前 API 明确仍是 `requested_provider=mock/active_provider=mock`，因此该结果只证明基础设施链路，不证明真实 Provider 或 31 场景业务结果。
- 科研证据质量门增量回归：`test_team_feedback_output_contracts.py`、`test_scenario_output_contract.py` 与 `test_agent_result_governance.py` 定向通过 `56 passed, 2 warnings`；研究场景现在确定性检查证据数量、用户最低数量要求、DOI/arXiv 覆盖、发布日期覆盖和来源链接覆盖，缺口会写入 `research_evidence_quality`/`limitations` 并阻断 `publishable`，完整证据包仍可通过；Ruff、2 个相关服务 Mypy 和 `git diff --check` 通过。该结果仍是 Provider-free 结构验收，不证明 G2-01/G2-06/G2-14/G2-15 在真实 Provider 上稳定召回。
- 科研审核计数与展示状态一致性增量回归：`ScenarioOutputContractService` 不再仅信任 `review_status=approved`；有候选条目时必须具备合法条目结构且 `approved_count` 覆盖全部展示条目，缺失/不一致会变为 `incomplete`、保留 `candidate` 展示并阻断 `publishable`。G2-01/G2-06/G2-15 反例及完整 G2-14 正例与场景输出合同定向共 `47 passed, 2 warnings`；仍需验证真实外部检索、审核服务、审批恢复和历史任务展示之间的权威审核信封不会被改写。
- 多模态电路语义拒答增量回归：`test_universal_academic_solver.py`、`test_team_feedback_scenario_matrix.py` 和 Solver 质量门定向通过 `115 passed, 2 warnings`；冻结基线/本地图求解回归另通过 `4 passed, 2 warnings`。新增组件端点映射必填、映射节点一致性和电压/电流源类器件极性或参考方向检查；相关服务 Mypy、Ruff、`git diff --check` 通过，`git diff --name-only -- apps/api/app/agents/solver_ct` 为空。
- 逐题视觉验收契约回归：新增 `app/services/visual_acceptance.py` 和 `test_visual_acceptance.py`，并把 G1 图片 fixture 的验收规格传入场景请求；视觉结构化输出对缺失 `must_capture/refuse_if_missing` 字段会记录 `visual_acceptance=blocked`、阻断 `can_continue` 并保留缺失项。视觉验收、通用 Solver 和场景元数据定向通过 `85 passed, 2 warnings`；Ruff、2 个相关服务 Mypy、`git diff --check` 通过。该结果仍是合成结构回归，不等同于真实图片经视觉 Provider 的逐题语义通过。
- 数学输出契约与安全降级回归：`MathFormattingService` 新增 `math_quality.v1`，非法 LaTeX 不再进入数学渲染器，而以代码段保留原文；`blocked/needs_review` 会同步到展示质量、场景 `quality_gaps`、`publishable=false` 和 `remaining_risks`。数学格式化/任务展示定向 `48 passed, 2 warnings`；31 场景输出契约、场景矩阵和任务展示定向 `116 passed, 2 warnings`；相关 Ruff、3 个服务 Mypy、`git diff --check` 通过。仍需用 G2-03/G2-07 原始输入和真实模型结果验证公式语义、单位和最终展示一致。
- G2-03/G2-07 公式输出契约增量回归：新增可选 `formula_output_contract.v1`，检查关键方程数量、带公式推理步骤、必需单位、关键语义标记和数学渲染质量；缺项会进入 `formula_output` 质量缺口、需复核展示和 `publishable=false`。公式契约/任务展示定向 `9 passed, 2 warnings`；相关 Ruff、3 个服务 Mypy 通过。该门禁是结构完整性检查，不替代符号等价、物理量纲和数值正确性证明，仍需 G2-03/G2-07 真实 Provider 回放。
- G2-03/G2-07 公式 AST/量纲增量回归：契约可显式要求 `require_formula_ast` 和 `require_unit_consistency`；公式会经过受限 SymPy AST 解析，结构化 `symbol_units` 可推导乘除、幂和加法量纲，解析失败、未知符号、等式两侧量纲不一致或预期输出单位不符都会进入 `formula_ast/formula_units` 缺口并阻断发布。新增正反例后数学/公式/任务展示定向 `55 passed, 2 warnings`，场景元数据筛选 `2 passed, 2 warnings`；仍需用真实 G2-03/G2-07 模型结果验证 LaTeX 变体、模型字段命名和领域公式正确性。
- 公式结构—最终展示断链回归：`math_quality.v1` 现在区分 `rendered_expression_count` 与 `structured_only_expression_count`；结构化结果中存在但未进入最终正文/数学片段的公式会产生 `structured_formula_not_rendered` 警告，并沿任务展示、场景质量缺口和 `publishable=false` 传播。公式、数学格式化、任务展示、场景目录和 31 场景筛选回归合计 `97 passed, 14 deselected, 2 warnings`；该检查仍不证明公式语义或数值正确。
- 会话历史质量状态回归：助手消息投影与 `/sessions/{id}/tasks` 历史接口现在保留 `math_quality`、`formula_output_contract`、`scenario_contract`、`requires_review`、`publishable` 及警告/剩余风险；没有场景合同但数学或展示明确需复核时，历史接口也显式返回 `publishable=false`，避免恢复后只看到公式正文而丢失发布门禁。新增历史质量契约与任务会话提交回归 `47 passed, 2 warnings`；Ruff、相关 Mypy 和编译检查通过。

此前阶段的 Provider-free 全量门禁结果如下：

- `test_team_feedback_scenario_matrix.py`：31 个脱敏场景输入均完成确定性路由回放；9 个图片场景通过输入能力预检；G2-16/G2-17 在携带上一轮科研上下文时仍进入电路求解，且记录 `context_boundary:research_not_reused`；
- `test_team_feedback_scenario_matrix.py`：新增从组员二原始 HTML 提取 17 个首个提问段落并逐项推进本地 Runtime；17 条均通过回放断言，其中 10 条完成，G2-01/G2-06/G2-14/G2-15 因外部检索未启用明确落入 `external_retrieval_unavailable`，G2-05/G2-12/G2-13 因模型能力未配置明确落入 `model_generation_required` 失败终态；
- 图片 fixture 回放：9 张原始反馈题图完成 SHA-256、PNG 格式、尺寸校验，并全部通过 `MultiImageComposer` 的单图视觉输入预处理；
- 科研证据回归：为 SiC/GaN 功率器件、多模态 LLM 视觉理解、边缘 YOLO 剪枝量化、RISC-V 侧信道防御和 CMOS OTA 增加显式复合主题过滤，确保跨主题候选不会直接进入答案；
- 定向回归：检索、研究前沿、31 场景矩阵、17 个输出契约和知识问答相关测试共 `113 passed, 2 warnings`；同时修复“仅有复合主题词时误删正确证据”的过滤器边界缺陷，并覆盖 LLM/YOLO 版本后缀；
- 电子学边界回归：旁路电容低频/部分旁路的合法“增益下降”表述不会再被首错规则或 AE 校验误报；与原有 G2-10/11/16/17 规则回归合计 `72 passed, 2 warnings`；
- Runtime 失败终态幂等：`TaskFailureService.fail()` 对已处于 `FAILED` 的任务直接返回，避免重复写入失败事件、终态运行记录和会话失败消息；新增回归并通过，定向测试 `18 passed, 2 warnings`；
- Runtime 失败原因保留：知识问答验证节点的部分失败现在向任务终态传播具体 `model_generation_required`，同时返回可操作的配置提示，不再退化为泛化 `runtime_execution_failed`；
- Runtime 错误码归一化增量回归：Runtime 节点产生的原始 `TimeoutError` 统一映射为 `provider_timeout`，Provider 结果缺失统一使用 `runtime_result_missing`（保留旧别名兼容重试），`provider_cancelled` 统一进入取消终态；新增执行服务/合同定向回归 `53 passed, 1 skipped, 2 warnings`，仍需真实 Provider、worker 和 SSE 断线场景验收。
- Runtime 终态竞争回归：成功、失败、取消在任务已进入任一终态后都不能互相覆盖；成功、异常失败、Provider 取消和排队态直接取消统一清理 `execution_owner/heartbeat_at/lease_expires_at`，并补齐取消错误分类和 `task_audit.v1` 终态更新。
- Runtime 取消可靠性增量回归：Provider 取消接口异常不再回滚排队任务已经写入的取消终态；失败/取消终态均清理 worker owner、租约并写入终态心跳。`test_task_terminal_boundary.py` + `test_task_cancel.py` 为 `22 passed, 2 warnings`，Runtime 执行/控制筛选回归为 `8 passed, 2 warnings`；仍需真实 worker、Provider 和断线重连场景验证取消竞态。
- Runtime 终态事件/审计对账增量回归：`task.failed`/`task.cancelled` 事件现在统一携带 `terminal_status`、`failure_category`、`error_code`、受限长度的 `error_message` 和 `runtime_run_id`，保留取消 `reason` 兼容字段；失败事件的 run ID 与 `task_audit.v1` 对账，Provider-free 定向回归 `13 passed, 2 warnings`，相关 Ruff/Mypy 通过。仍需真实 SSE 重连和跨进程事件读取验证字段顺序与一致性。
- Runtime 输出失败前置：输出契约校验失败现在在研究证据摄取和结果提交前抛出专用 `runtime_result_validation_failed`，避免无效结果进入记忆/研究库或被展示为成功。
- 路由与上下文一致性：路由重评后重新编译 `IntentExecutionPlan`；上下文装配按当前课程过滤历史消息，并覆盖无元数据旧消息，避免旧课程截断或串入当前任务。
- 会话连续性边界：滚动摘要现在在 `structured_state` 写入课程标识；任务后处理按任务课程生成摘要；上下文装配对未绑定或课程不匹配的旧摘要采取安全忽略，避免摘要跨课程污染。仍需补并发、恢复和摘要压缩场景的真实回放。
- 输出契约增量：求解器必须有独立 `final_answer`；课程必需结构遇到不可用状态会阻断；备课课时缺失/不匹配只保留可复核草稿，但合同状态为 `completed_with_gaps` 且不可发布；作业缺少首错时区分“证据不足可复核”与“证据充分应阻断”。
- 本轮最终定向组合回归：31 场景矩阵、输出契约、治理、场景合同和上下文隔离合计 `119 passed, 2 warnings`；首次组合回归发现 G2-02/G2-03/G2-08 的显式空列表被误判为硬缺失，已调整为可复核警告并复跑通过。
- 多模态拓扑安全门：视觉结构新增端点映射、极性和参考方向字段；确定性校验拒绝低置信度、含不确定项、重复标号、缺少端点或多器件断开的图；`can_continue=false` 不再被视觉边界判断绕过。Solver 相关回归 `118 passed, 2 warnings`。
- 非结构化视觉结果阻断增量回归：视觉模型无法解析为结构化对象时，现在明确写入 `visual_extraction_unstructured`、`visual_topology_validated=false` 并设置 `can_continue=false`，不会把自然语言摘要继续送入电路/拓扑推理；`test_universal_academic_solver.py` + `test_visual_acceptance.py` 为 `54 passed, 2 warnings`。
- 视觉连接标签边界补充：`unknown/uncertain/未知/不确定/未识别` 等伪确定节点现在进入拒答路径；专项 Solver 回归 `47 passed, 2 warnings`。
- 证据与发布边界：引用必需的场景在无可接受来源时明确拒绝；科研场景存在外部候选但 `review_status` 未批准/未完成时合同进入 `completed_with_gaps`，`publishable=false`，不能仅凭模型声称“证据充分”。证据、输出契约和外部 Runtime 回归 `24 passed, 2 warnings`。
- 外部证据审批前置：外部检索降级、审核失败或拒绝但仍保留候选时，Runtime 在回答节点前先进入 `external_research_evidence_review` 审批；恢复路径和直接调用旁路均二次清空未批准证据，只有显式人工放行后才可进入回答模型。科研 Runtime 定向回归新增旁路保护与“审批前模型调用次数为 0”断言。
- SSE/Runtime 事件协议：新增 `Last-Event-ID` 重连回归，验证重连只重放游标之后的事件，结合终态边界测试共 `19 passed, 2 warnings`。
- `test_team_feedback_output_contracts.py`：已有 18 个脱敏场景契约检查，并新增 12 条从组员二原始 HTML 提取的业务提问契约回放；整套测试为 `30 passed, 2 warnings`，覆盖必需字段、结构化结果和非伪造 JSON 展示；
- `task_audit.v1` 回归：新增 `test_task_audit.py`，并扩展任务状态、执行调试和 Runtime checkpoint 回归；验证输入/附件哈希稳定、run_batch/runtime run ID 写回、Runtime 节点 evidence/artifact ID 合并、成功输出合同记录、失败分类保留及指标合并不覆盖既有审计字段；定向审计与执行调试测试全部通过；
- 模型能力预检回归：`test_model_service_routing.py`、`test_task_router.py` 定向执行 `56 passed, 2 warnings`；覆盖可用模型路由、Provider 未配置、模态不支持、学习路径生成能力缺失和普通学习问答不误判；组员二原始 HTML Runtime 回放 `64 passed, 2 warnings`，G2-05/G2-12/G2-13 的创建记录均含生成能力缺失标记并保持 `model_generation_required` 失败契约；
- Agent 输入能力预检增量回归：显式场景目标与 fallback 现在统一校验输入类型、课程和意图；`AUTO/UNKNOWN` 作为研究任务中性课程不再被误判为能力缺失；任务创建对 Agent 停用、未发布、输入/课程/意图不支持和模型生成缺失分别记录终态错误码。路由/31 场景矩阵 `119 passed, 2 warnings`，新增能力分类测试 `6 passed, 2 warnings`；Ruff、相关 Mypy、`git diff --check` 通过。仍需将视觉、检索服务健康度和真实 Provider 可用性纳入同一能力矩阵，并完成真实多模态/外部检索验收；
- Runtime 执行计划能力快照增量回归：修复 `AgentExecutionPlanner` 使用 `setdefault()` 导致路由层能力预检无法覆盖本地旧值的问题；课程和意图改用最终 `RouteDecision` 判断，AUTO/UNKNOWN 及重路由意图不再产生假阴性；外部检索已禁用时，任务创建明确失败为 `external_retrieval_unavailable`，不再排队后才暴露缺陷。路由/执行计划/场景契约定向回归 `85 passed, 2 warnings`；仍需真实检索 Provider 健康度和真实多模态能力纳入矩阵。
- 外部检索硬依赖边界修正：课程知识问答中的外部检索是可选增强/回退，不能因配置关闭而阻断普通学习问答；只有科研前沿 Agent 或明确 `academic_search` 意图才标记为硬依赖。增加可选能力回归，组员二原始 HTML Runtime 回放更新为 `65 passed, 2 warnings`：10 条完成、4 条 `external_retrieval_unavailable`、3 条 `model_generation_required`。
- 场景课程合同回归：显式请求 AE 的学习路径合同绑定 AE，不再沿用 CT 演示案例课程；`AUTO/UNKNOWN` 保留演示课程回退并列为待产品决策风险；
- 路由修复：统一 `_decision_for_target` 的 `RouteDecision.availability`，修复 `local_solver_contract` 路径缺失 `input_mode_supported` 的契约缺口；学习路径、学生认知错误、Vivado/Verilog 时序诊断的优先级规则均有回归覆盖；
- `scripts/check.ps1`：此前阶段通过；本轮未重跑；
- 资源生命周期定向回归：`test_multimodal_rag.py`、`test_development_mock_agents.py`、`test_runtime_handoff_contract.py`、`test_document_ingestion.py` 合计 `40 passed, 2 warnings`；修复 Qdrant 本地模式 SQLite 探测连接泄漏，并让 `TaskLeaseManager.recover()` 将内部 SQLite 操作置于可收尾的子任务边界，覆盖生产 deferred startup 取消场景；
- 跨事件循环资源边界回归：`test_academic_writing_runtime.py`、`test_execution_debug_api.py`、`test_runtime_handoff_contract.py` 合计 `12 passed, 2 warnings`；执行调试持久化现在复用 TestClient 的应用事件循环，学术写作 Runtime 测试不再在同步测试中创建孤立事件循环；该定向范围只剩 Starlette/httpx 与 LangGraph 上游弃用提示，不能据此宣称全量 SQLite 警告已消失；
- 配置校验、敏感文件扫描、仓库布局检查：本轮通过；当前配置明确为 Mock Provider/local-only，未宣称真实 Provider 可用；
- Ruff：本轮 `apps/api` 全部通过；
- Mypy：本轮 `Success: no issues found in 322 source files`；
- Pytest：`1696 passed, 15 skipped, 11 warnings`，耗时约 `11 分 44 秒`；本轮收集 `1711` 项，新增审计链、原始 HTML Runtime/输出契约、课程合同、模型能力失败终态和资源生命周期回归均已纳入全量门禁；剩余警告未包含 aiosqlite 工作线程未处理异常或 Qdrant 本地探测连接告警；
- OpenAPI 导出：此前阶段通过，生成 `docs/api/openapi.json`；本轮未重导出；
- Docker Compose 配置校验：此前阶段通过；本轮未启动 Docker 服务，因此不等同于容器运行验收；
- Git 空白检查：本轮通过；仅有 `docs/api/openapi.json` 的 CRLF→LF 换行提示，不属于空白错误。

这次门禁证明当前代码和确定性回归没有破坏既有测试，但不改变本台账中的“未真实验收”状态：当前默认配置仍为 Mock Provider，尚未完成真实 Provider、真实外部检索、原始图片/文本逐题回放或生产/准生产部署验收。

本轮路由回放还确认了三项可复用规则：学习路径契约优先于“电路/方程/饱和”等学科关键词；学生陈述认知错误并要求诊断/验证题时进入作业诊断；Vivado/Verilog 时序问题进入数字电子课程知识路径，不进入科研检索或冻结求解基线。

## 六、下一轮执行入口

> 2026-08-22 长期执行状态补充：真实 Q01 后端闭环已达到 `mock_used=false`、视觉结构完整、模型完成、数学质量通过，但因 Edge 文件选择器和页面读取通道未稳定，不计 G1-Q01 Edge T2。当前 Docker 服务与 RAG 健康为 ready；只读模型缓存警告已通过 Hugging Face 离线模式消除，并用 `solver_series_current` 真实 Worker 回归验证 `mock_used=false`、24 个事件严格递增、DashScope `qwen3.6-flash` 完成。31 场景真实 Provider/Edge 证据包、科研证据、并发/重连和准生产门禁仍保持未完成。

> 2026-08-22 Showcase 增量：通用问答和知识问答真实 Runtime 均完成，知识问答使用 DashScope 并生成可追踪 RAG trace；通用问答虽 `mock_used=false`，但仍显示 `local_agent`、缺少独立模型名，不能把两条记录直接升级为内容质量通过。

> 2026-08-22 治理增量：真实科研写作回放曾暴露“证据不足但 accepted/publishable”的状态脱钩；已修复为 `accepted_with_warnings`、`publishable=false`、`requires_review=true`，并在真实容器任务 `task_348749015f35403a8a815286ebf12e23` 验证。备课/作业真实回放均完成但保留 `completed_with_gaps`，后续需补证据与人工复核闭环。

> 2026-08-22 科研检索增量：真实 `RESEARCH_01_ACADEMIC_SEARCH_V1` 任务 `task_5851a791781e4156acaf8c2ce2d6ae3a` 获取 6 条经审批的 arXiv/DOI 来源，事件顺序和来源字段完整；但模型综合发布门仍为 false，说明“检索证据通过”与“可发布科研结论”已被区分，后续需补 G2-01/G2-06/G2-14/G2-15 的逐条证据审计和 Edge 展示。

> 2026-08-22 数据分析真实金丝雀：任务 `task_811085d733bf4bcdaa6e0b9ca78e8039` 在受控真实 DashScope 配置下完成 24 行 CSV 分析，21 个 Runtime 事件严格递增、`mock_used=false`、无 fallback；`metrics.manual_review_required=true` 已与 `business_data.human_review_required=true` 对齐。修复了教学增强层误清除上游人工复核状态的真实状态一致性缺陷；金丝雀后默认冻结开关已恢复。

> 2026-08-22 Edge 文件权限状态：用户已允许 Edge 访问文件 URL，但本轮扩展控制通道在读取 `/workspace` 既有标签/DOM 时仍超时；因此 G1-Q01 仅保留后端真实视觉闭环证据，不计 Edge T2。

下一轮按以下顺序落地，完成一项就更新本台账对应行：

1. 继续扩展 G2-10、G2-11、G2-16、G2-17 的正反例与边界回归；组员二 17 条原始文本已进入本地 Runtime/输出契约回放，后续需补真实 Provider 结果绑定；
2. 基于已锁定的 G1-Q01–Q09 原始题图，继续补 `must_capture/refuse_if_missing` 对应的视觉拓扑、坐标、极性、单位、公式链和拒答结果逐题语义验收；当前通用端点映射/源类器件方向门已完成；
3. 在 `formula_output_contract.v1` 基础上继续建立 G2-03/G2-07 公式 AST/单位/推理步骤/最终展示四层 fixture，补齐符号等价、物理量纲和数值边界校验；本轮已补会话历史恢复的质量/发布状态保留，后续仍需对 `structured_formula_not_rendered`、`formula_ast` 和 `formula_units` 增加前端读取、SSE 重连和完整历史任务恢复回归；
4. 使用 `task_audit.v1` 的 `run_batch_id`、Runtime 节点 evidence/artifact ID 和输出合同字段，将当前 17 个组员二场景的原始文本回放结果补齐运行批次、证据包和最终展示版本绑定；对 G2-05/G2-12/G2-13 优先接入已发布且配置完整的模型能力；
5. 在配置完整且已发布的 Agent 上申请真实 Provider、真实检索和 SSE/Runtime 联调；
6. 重新执行本轮代码变更后的全量门禁；继续清理并分类剩余第三方弃用与资源未关闭警告；
7. 根据运行日志更新本表，并把剩余失败拆成代码缺陷、配置缺陷、证据缺陷、输入缺陷或外部依赖缺陷。

## 七、由本轮回放继续暴露的深层风险

这些风险不应等到真实 Provider 上线后才发现，后续应作为长期回归与发布门禁的一部分持续收敛：

| 风险类别 | 当前迹象 | 后续改造要求 |
| --- | --- | --- |
| 能力声明不完整 | 路由层原先只报告 Agent `local_ready/provider_available`，学习路径可能到执行阶段才发现缺少模型整理能力；显式场景目标和 fallback 还可能绕过课程/意图检查；执行计划还可能保留过期能力快照 | 已增加 `ModelService.preflight()`，把 `generation_required/generation_available` 写入选中路由；显式目标/fallback 统一校验输入、课程和意图；执行计划改用最终 `RouteDecision` 的课程、意图和布尔能力快照；外部检索关闭时任务创建明确失败。后续还要把检索 Provider 健康度、发布、视觉和真实 Provider 可用性纳入同一 capability 矩阵，并在 Runtime 恢复时复核不可变能力快照。 |
| `AUTO/UNKNOWN` 课程歧义 | 已记录演示课程回退来源和确认状态；唯一检测课程可在任务持久化前覆盖回退值 | 继续补真实会话的人工确认、课程切换和恢复回放；未确认时保持 `completed_with_gaps/publishable=false`，禁止把演示课程当作事实。 |
| 输出字段与证据脱钩 | 契约服务可以补齐结构字段，但不代表每个字段有足够来源 | 将字段级证据引用、推测标记、`publishable` 和人工复核状态绑定到展示层；证据不足时不能只显示“结构完整”。 |
| 原始输入绑定不足 | 已通过 `task_audit.v1` 固化输入/附件哈希、request/session/scenario、route、run_batch、Runtime run ID、终态、Runtime 节点 evidence/artifact ID 和输出合同版本；当前仍缺真实场景的证据包与最终展示版本闭环 | 为每个场景补充真实运行批次、证据包/来源快照、展示版本和差异比较；审计字段缺失时阻断“已验收”标记。 |
| 视觉语义缺口 | 当前 G1 图片证据主要证明字节完整、尺寸和预处理成功；代码已阻断缺少显式端点映射、映射不一致和源类器件缺少极性/参考方向的结构化结果，并支持 `visual_acceptance.v1` 对场景字段缺失拒答 | 继续把 Q01–Q09 的节点/拓扑/极性/单位/坐标/公式 AST 逐题绑定到真实模型回放；模型看不清或关键字段缺失时不得继续数值求解，并记录原图、结构输出和拒答证据版本。 |
| 研究检索漂移 | 主题过滤已有回归；研究场景又增加了证据数量、DOI/arXiv、日期和来源链接的确定性完整性门，但尚未在真实检索中证明时间窗、来源等级、去重和结论逐条引用稳定 | 为每个复合主题保存查询、排除词、候选来源快照和逐条证据；网络失败、结果不足、证据字段缺失和主题漂移必须分别呈现；对 G2-01/G2-06/G2-14/G2-15 做真实 Provider 回放。 |
| 数学输出与发布状态脱钩 | 已补 `math_quality.v1`；非法公式转为受保护代码，结构化结果中未进入最终正文的公式产生 `structured_formula_not_rendered`；启用公式契约时又增加受限 AST 解析和量纲一致性检查，相关警告同步到展示复核、场景质量缺口、剩余风险和 `publishable=false`；但尚未证明真实模型生成的公式语义、单位和结构化字段完整 | 为 G2-03/G2-07 增加公式 AST、单位、推理步骤、块级/行内渲染、结构化结果、SSE 重连和历史读取的一致性门禁；任何降级公式、只存在于 JSON 的公式、未知符号或字段/正文不一致都不得显示为已核验结论；补符号等价、数值边界和领域规则验证。 |
| 上下文与并发隔离 | 已修复摘要压缩时全局最新旧课程摘要和旧课程消息可能进入新课程摘要的问题；上下文缓存键已纳入资料发布状态版本；遗留摘要会回溯来源消息并拒绝撤回来源；科研外部证据现在只在同一科研链路、且完整审核通过的明确追问中连续复用，新显式检索不会携带上一轮证据，普通任务/电路诊断不会继承上一轮研究证据；真实 Redis 独立进程已验证写入、恢复和失效；G2-16/G2-17 已验证上一轮科研意图不改变路由 | 继续补双 API worker + 共享数据库的断线恢复、课程切换恢复、跨课程证据缓存失效和重复提交测试，并审计隐私字段是否进入提示词/日志。 |
| 终态与资源生命周期 | 失败原因已能传到任务终态；成功、失败和取消现在统一清除 worker owner、租约并更新终态心跳；本轮又统一了 Runtime 原始超时、结果缺失和 Provider 取消的错误码，避免同一根因在节点、任务、SSE 和重试层出现不同分类。变更前完整门禁为 11 条警告。本轮已修复 Qdrant 本地 SQLite 探测连接泄漏、生产 deferred startup 取消期间的 aiosqlite 收尾，并统一关闭 RAG 服务；同时消除了两个已定位的跨事件循环测试用法。仍有 10 条原始 SQLite 连接警告待定位，另有上游弃用提示 | 用最小复现继续追踪 SQLite/YAML 资源所有者，区分应用生命周期、TestClient、后台 worker 与第三方库；保留 TestClient/async_session 边界测试；补失败、取消、重试、重连、人工审批的 SSE 顺序和幂等测试，并验证 Runtime run、任务、事件和审计的终态字段逐项一致。 |
| 治理与发布边界 | 外部证据已增加回答前人工审批；课程资料撤回会失效索引/RAG 候选，上传资料 `kb-material` 原文接口、RAG 稀疏候选和历史结果/会话/聊天/调试投影也已拒绝撤回内容；管理员调试投影、运维观测面和内部调试页面已收口；原始知识资源已要求认证并禁止缓存，但授权、发布状态、隐私和可见性仍未全部端到端验收 | 继续对来源授权、版权、学生隐私、提示注入、人工审批、撤回/重新发布、日志留存和审计导出建立拒绝优先发布门禁；把发布状态绑定到静态资源读取，补最小权限运维角色、错误事件、CDN 缓存和未命名派生字段的反向扫描。 |
| 契约演进 | OpenAPI 与结构化场景合同已纳入门禁，但新字段仍可能造成旧客户端或展示层误读 | 为 Runtime、结构化结果、证据包和展示协议增加版本兼容测试，禁止通过无版本的字段重命名或静默改变含义。 |

## 2026-08-22 真实 Edge Q01 纠偏记录

- Edge 已允许文件 URL；通用 `/workspace` 成功选择并上传 `Q01_signal_convolution.png`，真实任务 `task_e4cf84d8fa914c5a978e7b5997a70962` 完成，`mock_used=false`、`fallback_used=false`、真实模型为 `dashscope/qwen3.7-plus`，视觉结构 `complete`。
- 结果展示曾因旧静态脚本缓存把真实 Provider 显示为 `local_graph`；新增生成溯源投影、前端 `workspace.js` 版本号后，Edge“回答信息”已显示 `实际 Provider=dashscope`、`Runtime 通道=local_graph`、`生成模型=qwen3.7-plus`，与 API 一致。
- 本次不能关闭 Q01：`visual_acceptance=not_configured`、场景证据审查未执行、`quality_gate=partial`、`math_quality=needs_review`（真实输出含 `unsupported_command:Big`）。
- 新增输入合同风险：`faculty_course_copilot_v1` 配置为 text-only，但带该 `scenario_id` 的页面在图片上传后提交为 `mixed` 并被拒绝；后续应绑定专用学术视觉场景，不应直接放宽教师场景输入类型。

## 2026-08-22 真实 Edge Q01/Q02 专用场景记录

| 场景 | 真实任务 | 真实模型与关键门禁 | 当前台账结论 |
|---|---|---|---|
| G1-Q01 | `task_b404f283dd674a0c9c9bde3a6675b4d1` | `dashscope/qwen3.7-plus`；视觉验收通过；模型完成；数学质量通过；字段无缺失 | 已完成专用场景真实回归；因证据 partial/人工复核，`completed_with_gaps`，不计发布通过 |
| G1-Q02 | `task_7ba07093d3e147f7b092b913ebfb7035` | 视觉与求解均为 `dashscope/qwen3.7-plus`；`visual_acceptance=passed`；`visual_topology_validated=true`；数学质量通过；字段无缺失 | 已完成专用场景真实回归；因课程确认/人工复核，`completed_with_gaps/publishable=false` |

本轮同时修复了视觉门禁误把频谱图的非关键刻度/箭头不确定性视为致命缺失的问题，并补充真实频谱输出所需数学符号白名单。两项真实任务均 `mock_used=false`；其余场景仍必须逐条取得 Edge 原始输入、附件哈希、Runtime/SSE/证据包和最终展示对账后才能关闭。

## 2026-08-22 G2-16 专用场景真实证据

| 场景 | 真实任务 | 真实证据 | 台账结论 |
|---|---|---|---|
| G2-16 | `task_2c0be8b54551426ea89970a7cee10127` | `academic_text_diagnostic_solver_v1/g2-16-bjt-cutoff`；`mock_used=false`；`dashscope/qwen3.6-flash` 完成；6 个答案支撑字段齐全；`quality_gaps=manual_review` | 真实模型与场景契约回归完成；因实验安全人工复核保持不可发布，不关闭 G2-16 T2 |

本轮新增纯文本电路诊断场景，修复直接按课程/意图创建任务时 `scenario_contract=null` 的审计缺口；字段只由真实答案中的可识别语义标记生成，不使用固定 Mock 内容补齐。G2-17 真实任务 `task_55ae950ed6164f978d3c2f92daa2bf5d` 也已完成真实回归，覆盖非理想诊断、补偿元件和验证步骤，但保留 `manual_review,math_rendering` 缺口，不能关闭为可发布通过。

## 2026-08-22 Q03 真实模型回归与新增缺口

| 场景 | 真实任务 | 真实证据 | 台账结论 |
|---|---|---|---|
| G1-Q03 | `task_127a3a3490a543518c7b39f073834641` | 原图真实上传；`mock_used=false`；视觉 `dashscope/qwen3.7-plus` 调用 2 次；`visual_acceptance=blocked`；题干事实覆盖 `prompt_facts_cover=true`；求解 `dashscope/qwen3.7-plus` 调用 1 次且完成 | 真实模型/Provider/Worker/求解链已回归；视觉语义未通过，`completed_with_gaps/publishable=false`，不关闭 G1-Q03 |

本次同时修复了一个代码缺陷：用户题干已经明确提供验收事实时，视觉门控策略允许继续求解，但下游边界仍只看 `visual_topology_validated`，导致真实模型调用被错误跳过。修复后保持“可继续求解 ≠ 视觉验收通过 ≠ 可发布”的三态分离。真实输出新增 `math_rendering` 缺口，后续必须把公式渲染、AST、单位和发布状态绑定，不能只看模型返回了答案。

## 2026-08-22 G2-10/G2-11 真实 Provider 与 Edge 回放

| 场景 | 真实任务 | 真实证据 | 台账结论 |
|---|---|---|---|
| G2-10 | `task_1f696d5488194a61882acc460dd3dff1`；Edge 回放 `task_5ec21ab6e3584aada03059841c01687b` | `TEACH_02_ASSIGNMENT_REVIEW_V1`；`mock_used=false`；`dashscope/qwen3.5-flash`；真实 Provider latency 12.9–13.9 s；`generation_provenance` 含 internal execution；契约字段 `first_error/error_cause/concept_correction/review_boundary` 齐全 | 真实模型、Runtime、场景契约和 Edge 提交链路完成；仍为 `completed_with_gaps/publishable=false`，需教师复核频率、信号源内阻和输入电阻定义 |
| G2-11 | `task_9884cc13cf704ff88061cb9543d28907` | `TEACH_02_ASSIGNMENT_REVIEW_V1`；`mock_used=false`；`dashscope/qwen3.5-flash`；真实 Provider latency 11.0 s；契约字段 `first_error/error_cause/verification_task/review_boundary` 齐全 | 真实模型与场景契约完成；仍为 `completed_with_gaps/publishable=false`，需教师复核静态/动态功耗边界与参数 |

本轮发现并修复两个深层契约问题：内部 Agent 之前只有 `mock_used=false`，但真实 Provider/模型没有投影到统一 provenance；现在持久化 `provider/model_route/provider_request_id/usage` 并在结果面板汇总。其次，`not_available` 映射曾被错误计入 `present_fields`；现在会进入 `missing_fields`。G2-10 的 `concept_correction` 仅从真实模型返回的 `teacher_feedback` 做来源标记映射，不生成固定文本。真实 Edge 任务事件为 26 条、序号 1–26 严格递增；Edge 控制通道随后在结果 DOM 读取阶段再次超时，因此该条以 Edge 提交 + API/SSE 对账计入链路证据，不把浏览器结果读取超时误报为内容通过。

## 2026-08-22 G2-10 Edge 真实复跑与语义一致性缺口

- Edge 专用 URL：`/workspace?scenario_id=assessment_diagnosis_v1&scenario_case_id=g2-10-bypass-capacitor`；真实任务 `task_c3c47e92b5b34d74a46d45b5f15bfb92`。
- 页面“回答信息”显示 Agent `TEACH_02_ASSIGNMENT_REVIEW_V1`、实际 Provider `dashscope`、Runtime 通道 `local_agent`、生成模型 `qwen3.5-flash`；API `mock_used=false`、生成溯源同样为 DashScope/Qwen。
- 结果契约字段 `first_error/error_cause/concept_correction/review_boundary` 齐全，资料状态 `partial`，场景 `completed_with_gaps`，`quality_gaps=manual_review_required`，`publishable=false`；30 条 API 事件序号严格 `1..30`。
- 真实模型已正确指出旁路电容会使交流增益增大，但同一输出一处将“输入电阻确实降低”列为正确，另一处又列为需要改进，暴露出比字段完整性更深的语义一致性缺口；现已加入“学生原判断—首错—纠正—验证题”之间的结构化一致性检查，发现矛盾时标记 `needs_review` 并禁止任何自动发布。

## 2026-08-22 G2-10 语义门修复后的最终 Edge 对账

- 最终真实任务：`task_3f3f12c43b4348c08982e40f57214790`；页面显示实际 Provider `dashscope`、Runtime 通道 `local_agent`、生成模型 `qwen3.5-flash`，API `mock_used=false`。
- 新增治理结果：`validation_status=warning`，`semantic_consistency.status=needs_review`；工作台“答案质量”已展示“输入电阻降低同时被列为错误和正确，需教师复核后才能使用”，不再只显示笼统的“需要复核”。
- 场景合同仍为 `completed_with_gaps`、`quality_gaps=manual_review_required`、`publishable=false`；API 事件 26 条，序号严格 `1..26`。该任务计真实 Edge/API/Runtime/SSE/治理链路完成，不计内容无缺口通过。

## 2026-08-22 G2-11 Edge 真实提交与功耗边界对账

- Edge 专用 URL：`/workspace?scenario_id=assessment_diagnosis_v1&scenario_case_id=g2-11-cmos-power`；真实任务 `task_7d94ed54f7884238b275aefbcdc81656`。
- 页面与 API 均显示 `TEACH_02_ASSIGNMENT_REVIEW_V1`、实际 Provider `dashscope`、生成模型 `qwen3.5-flash`、`mock_used=false`；Runtime 通道为 `local_agent`。
- 输出字段 `first_error/error_cause/verification_task/review_boundary` 齐全，模型明确区分静态功耗与 `P_dyn=C·V²·f` 动态功耗，并生成 1 kHz/1 MHz 对比验证题。
- API 事件 26 条，序号严格 `1..26`；场景为 `completed_with_gaps`、`quality_gaps=manual_review_required`、`publishable=false`。当前仍需教师确认静态功耗量级、负载/电压/翻转率参数和工艺漏电边界。

## 2026-08-22 G2-16 Edge 真实提交与电路诊断质量门对账

- Edge 专用 URL：`/workspace?scenario_id=academic_text_diagnostic_solver_v1&scenario_case_id=g2-16-bjt-cutoff`；真实任务 `task_9ad6b7419845418a93b614ec3ca2fe30`。
- 页面与 API 显示 Agent `ACADEMIC_PROBLEM_SOLVER`、实际 Provider `dashscope`、生成模型 `qwen3.6-flash`、`mock_used=false`；输出包含工作区判断、三个候选原因、逐项验证和安全边界。
- `quality_gate=partial`，具体缺口为 operating region、small-signal prerequisite、feedback polarity、unit consistency 尚无确定性覆盖；场景 `completed_with_gaps`、`publishable=false`。
- API 事件 24 条，序号严格 `1..24`。该任务计真实 Edge/API/Runtime/SSE/结构化字段完成，不计确定性内容零缺口通过。

## 2026-08-22 G2-17 Edge 真实提交与数学/字段门对账

- Edge 专用 URL：`/workspace?scenario_id=academic_text_diagnostic_solver_v1&scenario_case_id=g2-17-integrator-drift`；真实任务 `task_d2978ddb92d7457ab6de4bf96cde892f`。
- 页面与 API 显示 Agent `ACADEMIC_PROBLEM_SOLVER`、实际 Provider `dashscope`、生成模型 `qwen3.6-flash`、`mock_used=false`；输出说明输入失调、偏置电流、漏电和并联反馈电阻方向，并保留数据手册/实验安全边界。
- 结构化场景缺少 `compensation_component`、`diagnostic_steps`，数学质量为 `needs_review`，警告 `unsupported_command:gg`；工作台已显示“不得直接发布”。
- API 事件 24 条，序号严格 `1..24`；场景 `completed_with_gaps`、`publishable=false`。该任务暴露真实模型字段恢复和数学渲染仍需继续收敛，不计内容通过。

## 2026-08-22 G2-17 字段恢复与数学质量最终 Edge 对账

- 最终真实任务：`task_73f7739165af4cb083c16c692ce7e42f`；页面/API 显示真实 `dashscope/qwen3.6-flash`、`mock_used=false`。
- `present_fields` 已覆盖 `observation_summary/nonideality_diagnosis/compensation_component/diagnostic_steps/safety_boundary/review_boundary`，`missing_fields=[]`；`math_quality=passed`、0 warnings、`publishable` 仅受场景人工复核门阻断。
- API 事件 24 条，序号严格 `1..24`；最终场景仍为 `completed_with_gaps`、`quality_gaps=manual_review,manual_review_required`、`publishable=false`，不把数学通过误报为业务发布通过。

## 2026-08-22 G2-09 真实模型回归与通用 Agent 溯源修复

| 场景 | 真实任务 | 真实证据 | 台账结论 |
|---|---|---|---|
| G2-09 | `task_46a046bc2f024bacac448a3d4f54a43e` | `GENERAL_QUESTION_V1`；`mock_used=false`；`dashscope/qwen3.5-flash`；1 次真实模型调用；四个评分维度和四个等级均出现；无学生分数 | 真实模型与业务字段回归完成；结果不是学生批改，不计发布通过；仍需教师确认 FPGA 板卡、资源阈值和课程评分边界 |

本轮修复通用问题 Agent 的深层溯源缺口：真实响应此前只记录 `model_execution.models`，展示层无法从列表恢复真实 Provider，导致结果面板可能把 `local_agent` 适配器误当成生成 Provider。现在同时保存 `model_execution.providers`，并由统一 `generation_provenance` 投影 `dashscope/qwen3.5-flash`；保留 `provider=local_agent` 作为 Runtime 适配器字段，避免两个语义混淆。回归 Ruff 通过，通用问题与展示定向测试 `22 passed, 2 skipped, 2 warnings`。该任务另暴露 `\\sim` 数学命令未进入白名单，记入数学质量剩余项。

## 2026-08-22 G2-09 场景合同绑定与数学质量复验

- 新增 `rubric_generation_v1` 场景及 `g2-09-fpga-clock-rubric` 案例，修复 G2-09 之前只有通用 Agent 结果、没有 `scenario_contract` 的可审计缺口；同步更新场景目录计数和 API 合同回归。
- 真实任务 `task_c63b22090b8841d689825b5a0d7d2ad4`：`GENERAL_QUESTION_V1`，`mock_used=false`，真实 `dashscope/qwen3.5-flash`；`present_fields` 包含 `rubric_dimensions`、`rubric_levels`、`student_score_excluded`、`review_boundary`，`missing_fields=[]`，不产生学生分数。
- 真实数学质量复验任务 `task_055bb86b91254358ad543e6ceaffef97` 在加入 `20 ms \\sim 50 ms` 约束后为 `math_quality=passed`、0 个警告；`\sim` 已加入受限数学命令白名单。场景合同仍因缺少课程证据保持 `completed_with_gaps`，不计可发布通过。

## 2026-08-22 G2-08 真实模型与检索/时长回归

- 新增 `g2-08-mealy-moore-flipped-classroom` 场景合同。
- 真实任务 `task_54e946f966534eaa8cbdf326612c6f36` 使用 `TEACH_01_LESSON_PREP_V1`、DashScope `qwen3.5-flash`，`mock_used=false`，1 次模型调用；合同字段齐全，`duration_check=pass`（课前20+课内30=50分钟），`math_quality=passed`。
- 修复时间区间误求和、课前/课内时长抽取和 Mealy/Moore 强主题检索锚点，避免 ASM 资料冒充依据；真实结果仍为 `completed_with_gaps/publishable=false`，原因是课程证据和评价标准不足，保留教师审核边界。
- Compose 还暴露 API 内置 Worker 与独立 Worker 争抢 Redis lease，独立 Worker 退出；纳入双 Worker 准生产门禁。

### G2-08 最终 Edge 重放与展示修复

- 最终 Edge 任务 `task_de41531d7f8a4ea2a51888642d8d721d` 经真实 `TEACH_01_LESSON_PREP_V1` 完成，实际生成 Provider/模型为 `dashscope/qwen3.5-flash`，`mock=false`、`fallback=false`；审批 checkpoint 经本地测试审批后正常闭环，30 条事件序号严格为 1–30。
- 修复展示层把 Runtime 生成结果误判为“未生成模型答案”的问题：Lesson Runtime 的真实模型来源记录在 `generation_provider/generation_model`，不一定写入旧的 `model_execution.status`。现在页面保留“资料不足/待教师复核”结论，同时显示真实模型已完成，不再错误显示“本次未生成模型答案”。
- 该任务仍为 `completed_with_gaps`，`evidence_status=insufficient`；模型还暴露“课堂流程未满足请求的总时长约束”，因此仍不可发布。该问题进入 G2-08 内容质量和时长校验的后续清单。

### G2-08 时长修复后的最终真实重放

- 最终真实任务 `task_9e627ba9a8f2437893756382aff78f33` 使用 DashScope `qwen3.5-flash`，`mock=false`、`fallback=false`，实际生成已记录；输出明确区分课前 20 分钟与课内 30 分钟，`duration_check=pass`，总计 50 分钟。
- 修复了摘要/截止时间重复计时、课前活动被课堂复述替代，以及高置信本地路由在页面上被误显示为“后备路径”的问题；新增抽取、提示词、路由展示回归测试。
- 事件序号严格递增至 26 并以 `task.completed` 收尾；课程证据仍为 `insufficient`，因此维持 `completed_with_gaps/publishable=false`，不把真实模型生成误报为可发布结果。

## 2026-08-22 G2-05 真实模型、RAG 主题门与两周计划复验

| 场景 | 真实任务 | 真实证据 | 台账结论 |
|---|---|---|---|
| G2-05 | `task_299c8879d6aa49e3b33999bfcf7f753b` | `student_learning_path_v1/g2-05-bjt-two-week-plan`；`LEARN_01_LOCAL_RETRIEVAL_V1`；`mock_used=false`；真实 `dashscope/qwen3.5-flash`；`mode=learning_path_model_generation`；结构化输出恢复成功；14 个计划条目；`plan_horizon_check=passed`（请求14天/计划14天） | 真实模型与周期契约完成；RAG 主题门识别到检索结果缺少 BJT/三极管锚点，`evidence_status=insufficient`、`scenario_contract=completed_with_gaps`、`publishable=false`，不计可发布通过 |

本轮修复三个真实问题：一是 AE 检索曾以 MOSFET/石英晶体等无关片段满足“多个来源+分数”门槛，新增命名主题覆盖检查，缺少 BJT/三极管证据时清空回答依据并明确警告；二是学习路径提示不再硬编码 7 天，按用户“两周/四周/天数”请求生成周期检查；三是 Provider 返回 `day_1/day_2` 对象或嵌套周对象时先规范化为带 day 标记的数组，避免合法 JSON 因传输形状差异失败。对应回归：RAG/知识问答/场景合同定向测试通过；真实任务最终仍保持不可发布，避免“结构完整”掩盖“证据不足”。

## 2026-08-22 G2-12 真实模型、四周周期与人工复核发布门

- 最终真实任务：`task_5bb5130dcb8049dc94d5f7aafaf1b869`，`LEARN_01_LOCAL_RETRIEVAL_V1`，DashScope `qwen3.5-flash`，`mock_used=false`。
- 真实输出保留四个周阶段，`plan_horizon_check=passed`（请求28天/计划28天）；课程证据状态为 `sufficient`。
- 修复场景级 `manual_review_required` 未参与发布判断的问题；最终 `scenario_contract=completed_with_gaps`、`quality_gaps=manual_review_required`、`publishable=false`。
- 该任务仅计真实 API/Provider/结构化周期回归完成；Edge T2、教师确认、电源安全与实验条件审查仍未完成。

## 2026-08-22 G2-13 真实学习路径与教师复核门

- 真实 API 初始任务：`task_55f7584f312a483e8a4c86d083424fe2`；主题门修复后的最终 Edge 任务：`task_60dbbc1f5d0a4342923d342badf2d991`；均为 `LEARN_01_LOCAL_RETRIEVAL_V1`、真实 `dashscope/qwen3.5-flash`、`mock_used=false`。
- 结构化学习路径生成完成，课程证据状态为 `sufficient`；检索主题过滤保留了可用证据并记录被拦截片段警告。
- 复跑后新增拉普拉斯/极点/稳定性主题覆盖门：无命中主题证据时最终 `evidence_status=insufficient`、`source_refs=[]`，同时保留 `completed_with_gaps`、`quality_gaps=manual_review_required`、`publishable=false`。
- 仍需补真实对应教材证据、前后测证据绑定和教师对极点—时域响应—稳定性解释的复核；不能因模型生成了结构化计划而宣称内容可发布。

> Edge 观测补充：本轮早期 Edge 初始化曾连续超时，随后已恢复并完成 G2-05、G2-12、G2-13 的专用场景提交、结果读取和 API/SSE 对账；G2-13 复跑还验证了主题证据不足会在页面显示 `status: insufficient` 与 `0 / 0` 资料，不回退为伪造来源。

## 2026-08-22 G2-05 Edge 真实提交与展示对账

- Edge 专用 URL：`/workspace?scenario_id=student_learning_path_v1&scenario_case_id=g2-05-bjt-two-week-plan`。
- Edge 真实任务：`task_114f6e78ff6c49f0a8c8ed86b5f2b891`；`LEARN_01_LOCAL_RETRIEVAL_V1`；实际 Provider `dashscope`；模型 `qwen3.5-flash`；`mock_used=false`；Runtime `completed`。
- 页面“回答信息”与 API 一致显示：14 天阶段计划、实际 Provider、生成模型、资料 `0 / 0`、结果需复核；未把资料不足伪装成课程证据完成。
- API 事件回放 20 条，序号严格为 `1..20`；审计关联包含 session、scenario、input SHA-256、Runtime run、artifact 和输出合同版本。
- 该场景完成真实 Edge/API 链路验收，但内容结果仍为 `evidence_status=insufficient`、`completed_with_gaps`、`publishable=false`，不计可发布内容通过。

## 2026-08-22 G2-12 Edge 真实提交与发布门对账

- Edge 专用 URL：`/workspace?scenario_id=student_learning_path_v1&scenario_case_id=g2-12-power-training`。
- Edge 真实任务：`task_90d0b0810bc340529de6822cd77f4ce4`；页面显示实际 Provider `dashscope`、生成模型 `qwen3.5-flash`，API 对账 `mock_used=false`。
- 结构化结果按四周/28天通过周期门；课程证据为 `sufficient`，但场景人工复核策略生效，`completed_with_gaps`、`quality_gaps=manual_review_required`、`publishable=false`。
- API 事件 20 条，序号严格 `1..20`；产物 ID 为 `artifact_6ae788f102154da5be539082c41ada4f`。该结果证明 Edge 展示、真实 Provider、Runtime、SSE 和发布门状态一致，内容仍需教师安全复核。

## 2026-08-22 G2-13 Edge 真实提交、主题证据门与展示对账

- Edge 专用 URL：`/workspace?scenario_id=student_learning_path_v1&scenario_case_id=g2-13-laplace-physics`。
- 修复主题证据门后重新提交真实任务 `task_60dbbc1f5d0a4342923d342badf2d991`；页面与 API 均显示 `LEARN_01_LOCAL_RETRIEVAL_V1`、实际 Provider `dashscope`、生成模型 `qwen3.5-flash`、`mock_used=false`。
- 主题门正确拦截无关 CT 片段：`evidence_status=insufficient`、`source_refs=[]`、页面资料 `0 / 0`、答案需要复核；结构化路径仍可生成，但不再把课程泛化内容标成直接证据。
- API 事件 20 条，序号严格 `1..20`（`task.created` 到 `task.completed`）；场景合同为 `completed_with_gaps`，`quality_gaps=manual_review_required`，`publishable=false`。
