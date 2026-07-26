# 真实评测数据集接入指南

## 0. 本轮实现清单

新增统一 provenance/rubric 合同、JSON Schema、数据集 manifest、导入/校验/报告比较脚本和四种运行模式；继续复用原 `EvaluationRunner`、scorer、cache 和 report writer。评测数据流为：授权来源 → 去标识化 → 导入合同校验 → suite 过滤 → 原 sessions/tasks API → 多维 scorer → Git 忽略的报告目录。

评测本身不新增数据库表；执行记录沿用 tasks、agent_runs 和 traces。没有新增学生端评测 API，仍使用原任务 API；Workspace 只新增学习动作，调试页新增脱敏聚合指标。评测运行参数使用 CLI，私有目录和报告/缓存通过 `.gitignore` 管理。

## 1. 数据分层

- `synthetic`：仓库内合成样例，只用于合同和回归，不产生官方质量结论。
- `public`：公开来源，必须记录页面、许可证和允许用途。
- `licensed`：经授权数据，必须记录授权范围和到期条件。
- `private`：本地私有真实案例，必须去标识化，`publishable: false`，不得进入 Git。

私有文件放在 `evaluation/private_cases/`。`.gitignore` 默认排除该目录中除 README 外的全部内容。

## 2. 案例字段

统一 `EvaluationCase` 包含输入来源、课程、任务类型、难度、期望路由、必需知识点、禁止错误、结构化参考解、容差、rubric、judge 类型、证据要求和 provenance。JSON Schema 位于 `evaluation/schemas/`，默认权重位于 `evaluation/rubrics/default.yaml`。

人工评分材料应只存 rubric 结论和去标识化说明，不保存学生姓名、学号、联系方式、原始聊天记录或未经授权的教材正文。

## 3. 导入与验证

```powershell
.\.venv\Scripts\python.exe scripts\import_evaluation_cases.py input.json evaluation\private_cases\CT\cases.yaml --source-type private --authorization "本地授权记录编号"
.\.venv\Scripts\python.exe scripts\validate_evaluation_cases.py --root evaluation\private_cases
```

导入脚本支持 JSON、JSONL、CSV，并在落盘前执行 Pydantic 合同验证。授权文本不得包含真实密钥或个人身份信息。

## 4. 运行模式

```powershell
# 确定性本地链，不调用收费模型
.\.venv\Scripts\python.exe scripts\run_evaluation.py --mode local_deterministic --suite academic_solver --max-cases 3

# 本地 Mock，报告不得描述为真实模型结果
.\.venv\Scripts\python.exe scripts\run_evaluation.py --mode local_mock --suite task_reliability

# 真实模型或真实星辰，必须显式确认可能产生费用
.\.venv\Scripts\python.exe scripts\run_evaluation.py --mode real_model --confirm-paid --max-cases 3
.\.venv\Scripts\python.exe scripts\run_evaluation.py --mode real_xingchen --confirm-paid --max-cases 3
```

四种模式的报告必须分开保存和比较。HTTP 200、Provider 完成或配置完整都不等于答案质量通过。

## 5. 报告与比较

报告保留路由、结构、推理、数值、单位、引用和安全维度得分，并包含失败阶段、错误类型、模型/工具调用摘要、耗时和 trace id。报告目录和缓存目录均被 Git 忽略。

```powershell
.\.venv\Scripts\python.exe scripts\compare_evaluation_reports.py baseline.json candidate.json
```

比较脚本报告逐 case 分数差值和新增失败。模型裁判只能作为 `judge_type: model` 或 hybrid 的一部分，不能替代可执行数值/单位规则和人工复核。

## 6. 完成与未完成

已完成 schema、rubric、provenance、模式隔离、导入校验、统一 runner 扩展、报告比较和两个 synthetic/not_official 示例。未完成的是经授权的真实课程题目、人工参考解、人工 rubric 双人复核和真实模型/真实星辰正式跑分；这些仍需人工制作与验收。仓库示例、Mock 结果和本地确定性测试不得描述为真实数据或真实质量指标。
