# 科研数据分析 V2 设计合同

## 目标

`RESEARCH_03_DATA_ANALYSIS_V2` 的交付物不是对数据规律的自然语言总结，而是一个经过研究设计、数据质量、确定性执行、诊断、稳健性分析和人工复核的科研分析包。

科研检索结果只作为 `method_reference` 或 `experiment_protocol` 证据；用户数据只作为 `user_dataset`；两者不得混入同一无来源的上下文中。论文不能替代数据，数据结果不能自动生成论文事实。

## 工作流状态

```text
planning
  ├─ quality_blocked ──> planning
  ├─ insufficient_data ──> planning
  └─ ready_for_execution
       ├─ executed ──> needs_review
       ├─ quality_blocked
       └─ failed ──> planning
```

禁止从 `planning` 直接进入 `executed`。没有授权数据、数据契约或冻结的分析计划时，只能返回计划、阻塞原因或 `insufficient_data`。

## V2 输入合同

输入至少要明确：

- 研究问题、假设和分析目标
- 研究设计：两组/多组实验比较、重复测量、观察性回归、时间序列、小样本或预测
- 估计量和分析单位
- 变量角色、类型、单位和定义
- 数据集授权、版本、格式和 checksum
- 数据字典、研究设计/实验协议
- 软件环境和约束
- 方法证据引用

合同位置：`apps/api/app/contracts/research_analysis.py`。

## V2 结果合同

结果必须区分：

- `design_assessment`：研究设计是否支持问题
- `data_quality`：schema、单位、主键、缺失、异常和泄漏检查
- `plan`：冻结的分析计划及 hash
- `provenance`：数据集版本、格式、行列数、checksum、变量定义和软件环境；默认不包含本地 source_ref
- `artifacts`：脚本、表格、图、诊断和报告
- `effect_estimates`：效应量，而不是只给 p 值
- `uncertainty_summary`：置信区间、Bootstrap 或预测不确定性
- `diagnostics`：假设检查和模型诊断
- `robustness_findings`：替代方法、缺失处理和敏感性结果
- `interpretation`：科学解释和因果边界
- `limitations`：样本、设计、数据和外推限制
- `human_review_required`：科研结论默认需要人工审查
- `review_checklist`：与本次结果绑定的复核项；签字后形成带 hash 的审查记录

## 执行边界

LLM 只负责问题结构化、候选方法、解释和报告草稿；数值计算、统计检验、模型训练和图表必须由受控本地执行器完成。执行器必须记录输入 checksum、代码、依赖、参数、日志和输出 Artifact。

## MVP 顺序

1. 两组实验比较：效应量、置信区间、分布/方差检查和功效边界。
2. 观察性回归：变量角色、混杂/共线性、残差和不可因果化声明。
3. 时间序列预测：时间切分、基线、滚动验证和泄漏检查。
4. 小样本实验：Bootstrap、敏感性分析和证据不足门禁。

每类 MVP 必须同时有正常样例、数据质量失败样例、错误方法样例、跨主题污染样例和不可执行样例。

## 现有系统接入策略

- 保留 `RESEARCH_03_DATA_ANALYSIS_V1` 作为兼容入口，不修改冻结 Solver。
- 新合同先作为独立 v2 合同和状态机存在，再由 TaskRunner 通过版本化适配器接入。
- 继续使用非阻塞任务、进度事件、Artifact、SSE 和现有权限边界。
- 不默认复用前一轮科研检索的论文上下文，只有显式 `evidence_ids` 才能进入方法证据集合。
- 对分析后学术写作流水线，只允许传递已验证的分析 Artifact 和结论边界，不传递未验证的模型生成文本。

## 当前已落地的本地执行边界

- `ResearchDataQualityService` 只做元数据门禁；没有授权清单、变量角色、数据字典、checksum 或设计必需变量时，不允许进入执行。
- `ResearchAnalysisPlannerService` 根据四类 MVP 冻结主方法、诊断、稳健性检查、缺失值策略和结论边界，并用确定性 hash 识别计划是否被篡改。
- `ResearchLocalAnalysisExecutor` 只接受调用方显式传入的本地 CSV、TSV、JSON、XLSX 或 Parquet 文件，不读取论文、不访问外部服务、不使用会话记忆；输出目录也必须由调用方传入。
- 当前执行器已覆盖两组/多组比较、重复测量、观察性数值回归、时间序列一阶基线和小样本两组比较；会生成计划、脱敏数据 provenance、效应量、诊断、报告、汇总包和确定性 SVG 图形 Artifact，并记录 SHA-256。provenance 只保留数据集版本、格式、行列数、校验和、变量定义和软件环境，不写入本地 source_ref。
- 两组比较执行留一法范围和小规模精确置换敏感性；回归执行残差尺度和未调整/调整系数差异；时间序列执行两步基线误差和后半段窗口差异。它们是可审计的敏感性输出，不代表自动完成科学结论。
- 多组比较支持声明式多重比较策略：请求 `holm` 时输出 Holm 调整后的成对比较，请求 `none` 时只输出未调整的成对比较并保留人工复核提示；两组/重复测量支持显式请求的 Bootstrap 区间。所有重采样都冻结随机种子并写入计划 hash。原始数据出现缺失值、重复配对键或形状不一致时，执行被质量门禁阻断。
- XLSX/Parquet 缺少 `openpyxl`/`pyarrow` 时返回明确依赖阻断，不静默转换或猜测格式。

## 当前接入结果与剩余工作

1. 已由版本化适配器把 v2 请求映射到 TaskRunner；保留 `request_id`、`session_id`、`evidence_ids` 和数据集 checksum 边界，并验证 v2 不会绕过本地 Runtime 调用外部工作流。
2. `execute=true` 的 CSV/TSV/JSON/XLSX/Parquet 已接入受控附件路径：任务只能读取文件服务已登记的附件，执行前复制到配置化临时目录，结果写入配置化 Artifact 根目录下的任务隔离目录；用户提交的服务器路径和任意 `output_dir` 不会被使用。SSE/任务响应不广播原始行数据，任务读取会剥离 source/output 绝对路径。
3. `/workspace?scenario_id=research_data_workbench_v1&analysis_v2=1` 已增加研究问题、研究设计、分析目标、假设、变量角色、数据清单、数据字典、重采样和多重比较入口；没有结构化主数据时默认 `execute=false`，上传 CSV/TSV/JSON/XLSX/Parquet 后由前端自动生成受控 `data_manifest` 并启用本地执行。用户问题会同时进入 `research_question`、`canonical_input.text` 和 `canonical_input.data_description`；对于未填写的实验比较字段，前端根据用户问题与已提取的数据表头补齐设计、效应目标、结局变量和分组变量。V2 受控本地执行不依赖云端模型密钥，前端不接收服务器绝对路径。
4. 合成测试已覆盖正常四类 MVP、缺失、形状不一致、计划篡改、证据角色隔离、本地执行边界和旧治理兼容；真实本地 API 与前端资源冒烟已执行。

## 可复现本地演示

仓库提供 `scripts/research_analysis_demo.py` 作为不依赖外部服务的演示入口。它生成四类非敏感合成输入，依次运行两组比较、观察数据回归、时间序列基线和小样本实验，并在调用方指定的目录中保存输入、任务级 Artifact 与 `demo_manifest.json`。演示清单明确记录网络调用为 0、未使用外部证据，不能被解释为真实研究效果或市场指标。

真实试点材料进入 API 前可用 `scripts/validate_research_pilot.py` 做本地预检。预检器只校验 V2 合同、授权元数据、checksum、声明形状和质量门禁；`--check-data` 也只读取本地表格，不调用模型或外部检索，并且不在输出中暴露 `source_ref`。

PowerShell 运行方式：

```powershell
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe scripts\research_analysis_demo.py `
  --output-root .local_outputs\research-analysis-demo
```

剩余工作是生产化证据而非当前 V2 合同的绕过：以授权试点验证复杂真实设计、复现日志、隐私/伦理流程和商业证据；更复杂的重复测量、多因子设计和长期审查留存仍需按试点需求扩展。

当前适配器约定：`AgentRequest.options.research_analysis_v2` 才会启用 v2 分支；默认 `RESEARCH_03_DATA_ANALYSIS_V1` 行为保持不变。`execute=false` 只冻结计划，`execute=true` 必须提供授权 manifest、checksum 和已登记附件；Artifact 与临时目录由 `RESEARCH_ANALYSIS_ARTIFACT_ROOT`、`RESEARCH_ANALYSIS_TEMP_ROOT` 配置。模型主导模式默认优先调用 `DATA_ANALYSIS_LOCAL_V1`，把研究请求和受控表格内容以有界文本发送给 Qwen，路由失败时按 `data_analysis_explanation` 配置尝试 Spark。系统只负责解析、脱敏、截断和结果合同校验，不替代模型选择分析方法；模型输出必须标记人工复核，模型不可用或输出不合规时才回退到本地确定性执行器。`model_direct=false` 可显式关闭模型主导模式；v2 执行失败返回结构化失败状态，不启动外部工作流回退。
