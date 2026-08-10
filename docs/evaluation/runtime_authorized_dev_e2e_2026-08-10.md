# 授权开发环境 Runtime 端到端验证记录（2026-08-10）

## 结论

在用户授权的开发隔离环境中，四个非星辰顶层 Agent 已完成小样本的真实
Legacy/Runtime 成对执行。Runtime 路径实际写入了业务计划节点、checkpoint 与
Task 事件，未再使用 `compat-1` 的 Legacy 包装计划。该记录证明开发环境的真实
调用与前后端任务链可走通；它**不是**语义等价、答案正确率、生产 canary 或
default 发布批准。

所有原始任务、事件、checkpoint 与输出仅位于被 Git 忽略的
`.local_outputs/runtime_authorized_dev_e2e_20260810/`。本文不复制原始答案、
Provider 请求 ID、密钥、Flow ID 或私有路径。

## 授权与隔离边界

- 授权范围：开发环境、现有环境变量、所有非星辰工作流；本次实际执行四个本地
  顶层 Agent，各一条脱敏合成输入的 Legacy/Runtime 配对。
- 星辰：`XINGCHEN_ENABLED=false` 与
  `XINGCHEN_WORKFLOWS_DEFAULT_ENABLED=false`；没有调用或修改星辰工作流，
  也没有修改冻结的 `SOLVER_CT v1.0`。
- 数据库与存储：独立 SQLite 数据库和 `.local_outputs` 存储根；先执行现有
  Alembic 增量 migration 后启动 API。
- 发布：隔离进程临时设定 `AGENT_RUNTIME_RELEASE_GATE_REQUIRED=false`，只为了
  采集首批 Runtime trace；没有修改工作区 `.env`、没有设为 default、没有写入
  生产 release artifact。
- 模型：DashScope 连通性探针的三个配置模型均通过。Spark-X 本次未满足探针的
  `SPARK_OK` 回包约定，因此隔离 API 显式禁用 Spark 主链并允许既有 Qwen 后备。
- 外部检索：低强度检查中 Crossref、OpenAlex、Tavily、SearXNG、Aliyun IQS、
  Bocha 和 News RSS 返回完成；arXiv 出现限流/超时，作为可预期的外部依赖风险
  保留在科研案例 warnings 中。

## Runtime 成对结果

| Agent | Legacy / Runtime 终态 | 实际 Runtime plan | Runtime 节点 | checkpoint（Legacy / Runtime） | Task 事件（Legacy / Runtime） | 备注 |
| --- | --- | --- | --- | ---: | ---: | --- |
| `GENERAL_QUESTION_V1` | completed / completed | `general-qa-v1` | observe → 子 Agent execute → verify | 2 / 12 | 17 / 23 | Runtime 创建 1 个受控子运行 |
| `LEARN_01_LOCAL_RETRIEVAL_V1` | completed / completed | `knowledge-qa-v1` | execute → verify | 2 / 9 | 21 / 19 | 本地课程资料检索回答；结果明确标注非星辰生成 |
| `ACADEMIC_PROBLEM_SOLVER` | completed / completed | `solver-runtime-v1` | observe → retrieve → execute → verify | 2 / 15 | 18 / 23 | 使用本地学术求解图；未修改 `SOLVER_CT v1.0` |
| `RESEARCH_01_ACADEMIC_SEARCH_V1` | completed / completed | `external-research-v1` | intent → fetch → answer → verify | 2 / 15 | 25 / 27 | 出现 arXiv 限流/超时与论文复核超时 warning，但任务在受控降级下完成 |

八个 Task 的事件 sequence 均严格单调递增。Runtime 任务均无 Legacy fallback，
且目标 Agent 与请求的显式开发调试目标一致。

运行中还发现并处理了两项验证基础设施问题：

1. 空的隔离 SQLite 数据库在开发态不会自动建表；执行既有 Alembic migration 后，
   `/sessions` 与任务创建恢复正常。
2. `.env` 默认关闭多个 `AGENT_RUNTIME_*_ENABLED` 开关。只配置 launch mode 时会
   产生 `compat-1` / `legacy.execution` 包装计划，不能视为真实 Runtime。隔离进程
   显式启用四项服务后复跑，才得到上表的业务 Runtime plan。先前包装结果已排除
   在本记录的证据范围外。

## 前端到后端验证

使用浏览器访问隔离 API 的 `/workspace`：

1. 以游客模式进入；
2. 从真实输入框提交一条脱敏的电容电压概念问题；
3. 等待任务完成，页面显示课程资料计数、格式化公式、回答、资料入口和反馈入口；
4. 浏览器控制台 error 为 0。

页面明确显示“后备模型完成”和“主模型未完成”的提示。这与隔离测试中主动禁用
不稳定 Spark 主链一致，属于透明降级而非真实主链通过。UI 没有卡在“正在执行”
状态；此前的卡住现象是空隔离数据库导致任务创建失败，迁移后已消失。

## 可复现命令

先在隔离开发环境中：使用绝对 SQLite `DATABASE_URL` 执行
`python -m alembic -c alembic.ini upgrade head`，启动 API 时保持星辰关闭，并对这
四项能力设置 `AGENT_RUNTIME_*_ENABLED=true`、对应的 canary launch mode 与仅本次
采集所需的 release-gate 覆盖。随后运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_runtime_authorized_dev_e2e.py `
  --base-url http://127.0.0.1:8031/api/v1 `
  --output .local_outputs\runtime_authorized_dev_e2e_YYYYMMDD `
  --timeout-seconds 210
```

脚本通过 `POST /api/v1/sessions`、`POST /api/v1/tasks`、Task 轮询、事件读取与
`/debug/execution/{task_id}` 采集证据。它使用仅开发环境可用的 admin debug target
固定目标 Agent；如果实际 Agent 不匹配，会 fail closed，并且不读取或落盘意外
能力的结果、事件或调试输出。

### 完整 checkpoint 与结构套件打包

`/debug/execution` 故意不返回 checkpoint 的 `state_data`，因此浏览器调试投影不能
代替可重放 trace。新增离线打包器 `scripts/package_runtime_e2e_evidence.py`：它仅读取
同一次隔离执行使用的 SQLite 数据库和上述已捕获目录，提取唯一顶层 Runtime run 的
原始 checkpoint，调用 `audit_checkpoint_trace`，并把每个 Agent 的成对记录交给既有
`collect_runtime_canary.py` 生成 `authorized_paired` structural suite。

它不启动 API、不调用 Provider/模型/工具、不改 launch mode；若 checkpoint 中存在
敏感键、任务路由不一致、trace/版本不一致或输入不一致，会 fail closed，且不重写
checkpoint state。只能对受控且 Git 忽略的本地目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\package_runtime_e2e_evidence.py `
  --output .local_outputs\runtime_authorized_dev_e2e_YYYYMMDD `
  --checkpoint-sqlite .local_outputs\runtime-authorized-e2e.db `
  --authorization-ref user-dev-authorization-2026-08-10
```

输出为同一受控目录中的 `runtime_canary_manifest_*.json`、
`structural_suites/*.json` 和 `evidence_packaging_report.json`。结构套件通过仅证明
trace、身份、版本、输入哈希与非语义结构条件；它不生成、推断或代替独立语义审查。

对每个已通过结构门禁的 Agent，打包器还会生成同一受控目录下的
`semantic_review_inputs/*.json` 与 `semantic_review_judgements_template/*.json`。
前者保存与 suite input hash 对应的脱敏输入，后者的每个 case 都明确为
`needs_review`、缺少真实评审人和时间，不能直接作为 sidecar 或发布凭据。独立评审人
应在受控目录查看 structural suite 中的成对输出，复制并完成模板后，才可调用
`collect_runtime_semantic_evidence.py`。

本次已为 `GENERAL_QUESTION_V1`、`LEARN_01_LOCAL_RETRIEVAL_V1` 与
`RESEARCH_01_ACADEMIC_SEARCH_V1` 实际生成上述两类私有评审材料。它们均明确处于
`needs_review`，没有评审分数、责任人或发布结论；`ACADEMIC_PROBLEM_SOLVER` 因结构
性能门禁失败而没有生成评审包。

#### 本次已捕获工件的离线打包结果（2026-08-10）

实际对 `.local_outputs/runtime_authorized_dev_e2e_20260810/` 与同次隔离 SQLite
执行打包，未产生新的 Provider 调用。三个 Agent 已生成完整 checkpoint trace 和
`authorized_paired` structural suite，且各自的结构 gate 为通过：

| Agent | Agent / Runtime plan version | 结构结果 |
| --- | --- | --- |
| `GENERAL_QUESTION_V1` | `general-qa-v1` / `general-qa-v1` | 通过 |
| `LEARN_01_LOCAL_RETRIEVAL_V1` | `knowledge-qa-v1` / `knowledge-qa-v1` | 通过 |
| `RESEARCH_01_ACADEMIC_SEARCH_V1` | `external-research-v1` / `external-research-v1` | 通过 |
| `ACADEMIC_PROBLEM_SOLVER` | `solver-runtime-v1` / `solver-runtime-v1` | 拒绝：延迟回归超过 50% 阈值 |

学术求解这一对的 Legacy/Runtime 总延迟分别为 836ms / 1284ms，增幅约 53.6%。
打包器没有放宽阈值、没有写出该 Agent 的 structural suite；聚合命令因此以非零退出码
结束。这是预期的 fail-closed 结果。三个通过项也尚未具备发布资格：它们仍缺独立
语义 sidecar 和人工发布决定；学术求解必须先定位性能回归、修复后重新以同一输入配对。

#### 学术求解重复样本（2026-08-10）

为区分一次性波动与稳定回归，在同一隔离 API/Task/SSE/checkpoint 链路上又执行了三组
相同脱敏输入的 Legacy/Runtime 配对；该 Agent 走本地图工作流，未产生新的外部 Provider
调用。三组均完成、目标 Agent 匹配且 SSE sequence 严格递增。四组（含首次）延迟如下：

| 样本 | Legacy | Runtime | Runtime 相对变化 | 单 pair 结构结果 |
| --- | ---: | ---: | ---: | --- |
| 首次 | 836ms | 1284ms | +53.6% | 拒绝 |
| 重复 1 | 6634ms | 1104ms | -83.4% | 通过 |
| 重复 2 | 15860ms | 665ms | -95.8% | 通过 |
| 重复 3 | 181ms | 668ms | +269.1% | 拒绝 |

这证明延迟具有显著冷启动/缓存或宿主噪声，不能用单一均值宣称性能通过，也不能让快样本
掩盖慢样本。因此 Runtime canary evaluator 已增加每个 pair 的延迟和模型调用回归阈值；
即使聚合总延迟下降，只要任一 pair 超过默认 50% 阈值，suite 仍 fail closed。学术求解
在出现可解释且可复现的性能界限前保持 Legacy，且不得把两个通过的重复样本视为发布批准。

## 仍未满足的发布条件

- 每个 Agent 仍需由独立评审人对脱敏 Legacy/Runtime 输出给出语义 judgement；
  不能由本次自动化结果代替。
- 三个结构通过项仍需按
  [授权成对 trace Runbook](runtime_authorized_paired_trace_release_runbook.md)
  收集 semantic sidecar，并使 release preflight 返回 `release_eligible=true`；学术求解
  需先修复性能回归并重新生成 structural suite。
- 需由发布责任人明确决定 canary 观察范围、通过阈值、观察期与是否切换 default。
- Spark-X 回包/提示词合同需要单独修复或重新验证，才可将“主模型完成”作为通过项。
- Docker、生产数据库/Redis/MinIO 与真实生产配置均未执行，不应从本次隔离验证
  外推为生产就绪。
