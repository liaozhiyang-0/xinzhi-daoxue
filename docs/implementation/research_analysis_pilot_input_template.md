# 科研数据分析 V2 授权试点输入包模板

本模板用于真实试点准备，不包含真实数据、真实客户信息、论文结论或市场数字。未能由试点方提供并核验的字段必须填写“待补证据”，不能用合成值代替。

## 1. 试点基本信息

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `pilot_id` | 是 | 试点内部编号，不使用姓名或身份证号 |
| `research_question` | 是 | 可检验的研究问题 |
| `hypothesis` | 验证性分析必填 | 预先声明的假设；探索性分析需明确标记 |
| `design` | 是 | `experimental_comparison`、`multigroup_comparison`、`repeated_measures`、`observational_regression`、`time_series` 或 `small_sample` |
| `estimand` | 估计效应时必填 | 明确要估计的量、单位和时间范围 |
| `unit_of_analysis` | 是 | 行与研究单位的对应关系 |
| `study_design` | 是 | 分配机制、测量时点、排除规则和协议版本 |

## 2. 数据与授权

必须随任务提交：

- 脱敏后的 CSV、TSV、JSON、XLSX 或 Parquet 文件；
- 数据字典，包含变量含义、单位、编码、缺失值和测量时点；
- `row_count`、`column_count`、格式、版本和 SHA-256 checksum；
- 数据授权证明、伦理/隐私审批状态和允许用途；
- 是否含敏感数据、脱敏方法和最小留存期限；
- 试点方指定的研究协议或方法参考来源。

没有授权或 checksum 的数据只能生成计划，不能进入 `execute=true`。

提交 API 前可先运行本地预检器。它只读取请求合同和（可选）本地表格的 checksum/形状，不调用模型或外部检索，也不会把 `source_ref` 写入报告：

```powershell
.venv\Scripts\python.exe scripts\validate_research_pilot.py `
  --request-json <试点请求 JSON> `
  --check-data
```

只有输出中的 `valid=true` 且 `ready_for_execution=true` 才进入 `execute=true` 流程；失败报告应随试点材料保存。

## 3. 变量登记表

| `name` | `role` | `dtype` | `unit` | `description` | 证据来源 |
| --- | --- | --- | --- | --- | --- |
| 待试点方填写 | `outcome` / `treatment` / `exposure` / `control` / `time` / `identifier` / `feature` | 待核验 | 待核验 | 待试点方填写 | 数据字典或协议 |

角色不能只凭列名猜测。重复测量必须登记 `identifier`；时间序列必须登记 `time`；回归中的控制变量必须说明是否为结果发生前变量。

## 4. 方法与证据登记

每个方法参考至少登记：

```json
{
  "evidence_id": "method-001",
  "role": "method_reference",
  "title": "待补证据：由试点方填写",
  "source_ref": "待补证据",
  "cited": false
}
```

在来源、版本和适用范围完成核验前，不能把方法参考写成“已证明适用于本数据”。论文或外部检索结果只能作为方法证据，不能充当用户数据集。

## 5. 试点验收记录

每次运行应保存：

1. 原始请求合同和冻结计划 hash；
2. 数据版本、checksum、环境和运行命令；
3. 质量门禁结果及所有阻断项；
4. 估计量、区间、诊断、稳健性和科学限制；
5. Artifact 文件及 SHA-256；
6. 研究者/统计师复核清单和签字记录；
7. 失败、重跑、修改原因和最终采用版本。

试点应单独记录复现耗时、人工修改次数、失败原因和研究者判断。工程合成测试不计入真实复现率、节省时间、准确率、收入或客户效果。

## 6. 本地演示与真实试点边界

合成演示：

```powershell
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe scripts\research_analysis_demo.py `
  --output-root .local_outputs\research-analysis-demo
```

真实试点必须由授权方提供数据、数据字典、协议、隐私材料和方法来源后单独运行。没有这些材料时，系统应停留在计划或 `insufficient_data`，不得生成真实研究结论。
