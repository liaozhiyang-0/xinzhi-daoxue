# 六门课程测试题统一格式

本目录保留原始题库和六门课程知识库源文件，不移动、不改写原文件。
转换脚本只在 `统一格式/` 下生成可复现的测试数据。

数据按用途提供四种视图；派生答案集和均衡套件会复用源题，数量不能直接
相加：

- `all_cases.json/jsonl`：四门课原始真实题库中核验通过、带参考答案的
  121 题。
- `supplemental/all_questions.json/jsonl`：从六门课程知识库课后习题中
  补充提取的题干和题图，`reference_answer` 固定为 `null`，不提取、
  不生成答案。
- `curated_answer_sets/all_selected_cases.json/jsonl`：从无答案补充题
  中精选的 48 题小规模测试集，其中 24 题带标准化参考答案、12 题带
  参考答案和合成学生错误步骤、12 题测试边界处理能力。
- `balanced_336/all_cases.json/jsonl`：最终推荐批测套件，共336题，
  六门课各56题；完整包含已有答案题和48题精选集，再以无答案题按章节
  分层补齐。

`all_test_inputs.json/jsonl` 是两层数据的可提交合集。它方便执行模型
输入测试，但其中无答案补充题只能人工判定，不能直接用于自动准确率统计。

## 统一格式

每条记录采用仓库现有 `EvaluationCase` 字段，可直接由
`apps/api/app/evaluation/loader.py` 对 `{cases: [...]}` JSON 加载：

- `case_id`：稳定且全局唯一的样例编号。
- `course`：项目课程 ID：`CT`、`AE`、`DE`、`SS`、`DSP`、`COMM`。
- `message`：只包含题目文本，不包含参考答案。
- `file_refs`：只包含题目输入图，路径相对本目录，附带媒体类型和
  SHA-256；答案图不会作为模型输入。
- `input_type`：按题图数自动设为 `text`、`text_and_image` 或
  `text_and_multi_image`。
- `reference_answer`：原题库参考解答；无答案补充题固定为 `null`。
- `structured_input.reference_answer_assets`：原题答案中的图像证据，
  仅供判分或人工复核，绝不会上传为模型输入。
- `requires_manual_review`：确认有问题的题已被排除，当前生成题均为
  `false`。
- `provenance`：统一标记为私有、本地、不可发布题库。

生成文件：

```text
统一格式/
├── all_cases.json                 # 核验后的四门原始真实题
├── all_cases.jsonl
├── all_test_inputs.json           # 原始题 + 六门无答案补充题
├── all_test_inputs.jsonl
├── question_bank_inventory.json   # 独立题目总数与各课程统计口径
├── dataset_manifest.json          # 原始题核验及排除记录
├── cases/                         # 原始题按课程拆分
├── jsonl/
├── supplemental/
│   ├── all_questions.json         # 只含题目、题图，不含答案
│   ├── all_questions.jsonl
│   ├── excluded_questions.json    # 不完整、重复、缺图等排除记录
│   ├── manifest.json
│   ├── cases/                     # 六门课按课程拆分
│   └── jsonl/
├── curated_answer_sets/
│   ├── part1_standard_answers.json
│   ├── part2_error_detection.json
│   ├── part3_boundary.json
│   ├── all_selected_cases.json
│   └── manifest.json
├── balanced_336/
│   ├── all_cases.json             # 推荐：六科各56题
│   ├── all_cases.jsonl
│   ├── manifest.json
│   ├── cases/                     # 按课程拆分
│   └── jsonl/
└── supplemental_assets/           # 从教材复制出的题图
```

## 生成与校验

在仓库根目录使用 Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\normalize_dataset.py
.\.venv\Scripts\python.exe .\真实测试题\extract_course_exercises.py
.\.venv\Scripts\python.exe .\真实测试题\validate_dataset.py --project-contract
.\.venv\Scripts\python.exe .\真实测试题\build_curated_answer_sets.py
.\.venv\Scripts\python.exe .\真实测试题\validate_curated_answer_sets.py
.\.venv\Scripts\python.exe .\真实测试题\build_balanced_suite.py
.\.venv\Scripts\python.exe .\真实测试题\validate_balanced_suite.py
```

两个转换器只使用 Python 标准库；`--project-contract` 会额外调用仓库
当前 Pydantic `EvaluationCase` 契约，建议每次题库变更后都运行。

补充提取器采用以下保守过滤规则：

- 与核验后的真实题库重复，或在补充题中重复；
- 题干过短、夹带独立答案段；
- 依赖另一道习题才能独立理解；
- 引用了题图但未能提取对应图片；
- 引用了题表但题表未嵌入题干。

原始题和知识库补充题还会执行多图完整性审查：若一道题由多张题图组成，且其中
存在宽度小于 120 像素或高度小于 80 像素的公式、变量或数值碎片，
则判定题面信息严重割裂并从生成数据排除。该规则不会删除原始资料，
也不会排除由多张完整电路图或完整曲线图组成的正常多图题。

所有排除项和原因都写入
`统一格式/supplemental/excluded_questions.json`，源教材不做删除。

## 48 题精选答案与边界集

为了控制答案生成和真实 API 批测耗时，精选集固定为每门课 8 题：

- 第一部分 50%：24 题，每门课 4 题，提供结构一致的参考步骤和结论。
- 第二部分 25%：12 题，每门课 2 题，提供参考答案以及可直接传入
  `student_attempt` 的合成错误步骤。
- 第三部分 25%：12 题，每门课 2 题，覆盖缺图、缺少上题、条件矛盾、
  定理前提、ROC 缺失、非法概率和未知逻辑状态等边界。

这些答案是根据题面推导并经过公式、数值交叉核算的标准化参考答案，不冒充
教材官方答案，且保持 `official_scoring=false`。第二部分使用项目现有的
`check_my_work`、`StudentAttempt.steps` 和 `expected_error_type` 协议。

## 六科均衡336题套件

推荐正式批测使用 `balanced_336/all_cases.json`：

- CT、AE、DE、SS、DSP、COMM 各56题。
- 121道核验后的原始答案题全部保留。
- 36道新增标准答案或查错题全部保留。
- 12道边界能力题全部保留。
- 从无答案题中按章节轮转、稳定排序补入167题。
- 共169题带参考答案或边界期望，167题为纯输入测试。
- 派生答案题会替换对应无答案源题，不重复计数。

## 直接提交本地 API

先预览核验后的四门真实题：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\run_api_tests.py `
  --course CT --max-cases 2 --dry-run
```

预览六门课补充合集（例如数字信号处理）：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\run_api_tests.py `
  --cases .\真实测试题\统一格式\all_test_inputs.json `
  --course DSP --max-cases 2 --dry-run
```

预览48题精选集中的查错样例：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\run_api_tests.py `
  --cases .\真实测试题\统一格式\curated_answer_sets\all_selected_cases.json `
  --case-id CUR-ERR-DE-001 --dry-run
```

预览均衡套件中的某门课程：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\run_api_tests.py `
  --cases .\真实测试题\统一格式\balanced_336\all_cases.json `
  --course COMM --max-cases 2 --dry-run
```

确认本地 API、数据库、Redis、MinIO 和所需 Provider 均已启动后，可去掉
`--dry-run`。脚本会为每题创建独立会话、上传题图、调用现有
`POST /api/v1/tasks`，轮询终态，并将原始结果写入
`统一格式/reports/`。

批测脚本只记录任务状态和原始结果，不把“任务完成”当成答案正确，也不
自动声称模型达到某个准确率。完整补充题仍没有答案；48题精选集可以作为
小规模参考评测，但在专家复核前不作为官方准确率数据。

## 评估指标与可视化

正式全量测试前的指标口径见：

- `EVALUATION_STRATEGY.md`：正确率、失败、耗时、Token、分母和阈值说明；
- `evaluation_metrics.json`：机器可读的指标与初始预警线；
- `visualization_strategy.json`：仪表盘、图表和字段映射；
- `analyze_evaluation_report.py`：将 EvaluationRunner JSON 汇总为指标
  JSON、逐题 CSV 和可视化数据；
- `validate_evaluation_metrics.py`：用合成小样本核验统计公式，不调用
  模型或 API。

口径自检：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\validate_evaluation_metrics.py
.\.venv\Scripts\python.exe .\真实测试题\validate_judgement_strategy.py
```

注意：默认规则评分器不会仅凭 `reference_answer` 自动判断 145 道普通
答案题的学科正确性。正式准确率要求结果中具有独立、可审计的
`actual.answer_evaluation`；缺少时分析脚本输出 N/A，而不是把任务完成
当作答对。12 道查错题使用专项合同评分；167 道无答案题始终只评运行、
路由、稳定性、耗时和资源消耗。

## 一体化全量测试

`run_full_evaluation.py` 在进程内复用现有 EvaluationRunner、TaskRunner、
Provider、RAG 和模型追踪器，并补充本地题图上传、逐题进度、每题检查点、
执行缓存、答案判分缓存和最终指标汇总，不需要另起一套 API 服务。

先执行无请求预检：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\run_full_evaluation.py --validate-only
```

确认 Provider 配置和可能产生的真实模型费用后，执行完整 336 题：

```powershell
.\.venv\Scripts\python.exe .\真实测试题\run_full_evaluation.py `
  --live --confirm-paid --judge-answers
```

其中 336 次智能体任务调用用于测试；`--judge-answers` 还会对 145 道普通
答案题按“内容哈希复核 → 确定性规则 → 三行简易模型判分”处理。查错题和边界题使用专项合同评分，不额外做
普通答案相似度判分。自动判分仍是非官方结果，后续需要分层人工抽查。

脚本默认每题写入检查点。中断后重新执行同一条命令会复用逐题执行缓存和
答案判分缓存；若只想重跑执行失败项，可增加 `--rerun-failed`。不要在恢复
运行时使用 `--no-cache`，否则会重新产生模型调用。

每次运行的结果位于：

```text
真实测试题/统一格式/evaluation_reports/full_live_<UTC时间>/
├── run_manifest.json
├── raw/
│   ├── latest.json
│   └── latest.md
└── metrics/
    ├── metrics_summary.json
    ├── case_metrics.csv
    └── visualization_data.json
```

## 已排除的原始数据问题

- 信号与系统顶层题库与
  `signal_systems_original_question_bank_48/` 中 181 个对应文件的
  SHA-256 完全一致。转换时只读取顶层副本，但不会删除重复目录。
- 模电 `AE-1-5-6` 题干不完整且缺少参考答案，已从生成数据排除。
- 数电 `DE-10-2-3` 缺少参考答案，已从生成数据排除。
- 数电 `DE-2-2-2`、`DE-2-3-1` 的题目与答案转录存在明显文字/公式
  差异，已从生成数据排除。
- `CT-C04-Q01` 等 41 道 CT 多图题由主图和微小公式、变量或数值图块
  共同承载题意，信息严重割裂，已从所有生成题集排除；完整清单和阈值
  记录在 `统一格式/dataset_manifest.json`，原始 Markdown 和图片保留。
- 数电 `3.2.11`、`6.1.7`、`7.1.4` 在答案汇总中缺少标准题号标题，
  转换器通过稳定文本边界恢复，并保留 `answer_boundary_inferred` 标记。
