# Agent Runtime 并行开发与质量协作规范

状态：执行规范 v1.0
适用范围：`xinzhi-daoxue` 的 Agent Runtime 长期迁移工作
维护者：主集成 Agent
最后更新：2026-08-09

本文是后续多进程、多 Agent 开发的操作规程。它不是架构愿景，也不是任务清单；每个并行任务都必须能够依据本文确定负责人、可写文件、依赖、验证命令和停止条件。

## 1. 基本规则

本文使用以下规范性词语：

- **必须（MUST）**：违反即停止任务并回报，不能以“之后再修”带过。
- **应该（SHOULD）**：除非在任务声明中说明原因，否则按此执行。
- **可以（MAY）**：由负责人根据任务需要选择。

并行开发遵循六条总规则：

1. 每个任务只有一个写入负责人；每个进程都必须声明与其他进程不相交的 `disjoint_write_set`，其他 Agent 默认只读、评审或提供建议。
2. 文件范围比功能描述更优先。任务声明没有列出的路径不得修改。
3. 共享接口先冻结再并行实现；发现接口需要改变时，先暂停实现并由主集成 Agent 更新契约。
4. 每个提交只表达一个可回滚的目的，并在提交前验证“只改了声明范围”。
5. 任何不确定的 Provider、凭据、迁移、冻结 Solver 或任务协议行为，都按高风险处理并停止扩散。
6. 合并以可复现验证为准，不以“本地看起来能跑”或单个 Mock 结果为准。

## 2. 协作拓扑与角色

### 2.1 主集成 Agent（Integrator）

主集成 Agent 是当前长期目标的唯一整合入口，负责：

- 把长期路线拆成可并行的任务，分配 `TASK-ID`、依赖和文件锁；
- 维护共享契约、合并顺序、发布门禁和回滚点；
- 审查每个 Agent 的声明范围、测试证据和敏感文件扫描；
- 按依赖顺序 cherry-pick 或合并经过验证的独立提交；
- 运行跨角色回归，决定 canary、default 或停止迁移；
- 记录未执行的 Docker、真实 Provider 和外部授权步骤，不把它们误报为已验证。

主集成 Agent 不应为了“方便合并”直接修改其他角色正在工作的文件。需要跨边界修改时，应先撤销对应文件锁、重新声明任务，并通知原负责人。

### 2.2 前端 Agent（Frontend）

负责 Runtime 的可见性和控制面，不负责执行编排逻辑：

- 展示 Run、节点、checkpoint、暂停、恢复、等待输入、审批和失败原因；
- 消费现有 Task 查询和 SSE 合同，处理断线重连、重复事件和终态展示；
- 提供人工审批、用户补充输入和恢复操作的交互确认；
- 对用户可见字段做脱敏，不显示 Prompt、完整 trace、向量、凭据或绝对路径。

前端 Agent 不得把 Runtime、RAG、Provider、TaskRunner 或重试逻辑复制到浏览器；页面加载和按钮渲染不得直接触发未经任务队列控制的 Provider 调用。

### 2.3 Runtime 后端 Agent（Runtime Backend）

负责 Runtime 内核和业务适配器：

- Goal、Plan、Node、Observation、Decision、Budget 和状态迁移；
- durable Run/node/checkpoint 的读写、恢复、乐观锁和幂等执行键；
- 工具、Provider、内部 Agent/子 Agent 的受控 handler；
- `observe -> decide -> act -> verify -> replan` 闭环；
- Runtime 与 Task/SSE/Provider 的兼容边界和失败传播。

Runtime 后端 Agent 不得把新的业务分支直接塞进大型 `TaskRunner`，也不得通过路由同步执行 Provider。新能力优先注册版本化 handler，再由 Runtime 计划调用。

### 2.4 评测/安全 Agent（Evaluation & Security）

负责独立证据和发布风险判断：

- 构造脱敏、版本化、可重放的 golden、failure、boundary 和 regression cases；
- 检查结构化结果、证据完整性、重规划、恢复、SSE 顺序、非阻塞和凭据隔离；
- 维护离线评测和 semantic evidence 的 provenance，不把 Mock 结果称为真实 Provider 结果；
- 审查权限、审批、提示注入、路径穿越、参数污染、敏感信息泄露和失败降级；
- 对 canary/default promotion 给出独立的 pass、pending 或 blocked 结论。

评测/安全 Agent 默认不改生产 Runtime 代码。发现代码缺陷时提交可复现失败证据和最小修复建议；若需要补测试，必须在任务声明中列出精确测试文件，并避开 Runtime Agent 已锁定的测试文件。

## 3. 互斥写入范围

### 3.1 默认文件归属

下表是默认锁，不代表可以绕过任务声明。`共享锁` 文件任何时刻只能由一个被指定的负责人写入。

| 角色 | 默认可写范围 | 默认只读范围 | 禁止越界 |
|---|---|---|---|
| 主集成 | 本文档、整合分支上的合并提交和临时验证输出 | 所有角色代码与测试 | 不直接重写角色实现以消除冲突 |
| 前端 | `apps/api/app/static/**`、明确声明的前端相关测试文件 | `apps/api/app/runtime/**`、Provider、数据库和评测输入 | 不改 API/Pydantic 契约来适配页面 |
| Runtime 后端 | `apps/api/app/runtime/**`、`apps/api/app/services/runtime_*.py`、`apps/api/app/repositories/agent_runtime.py`、明确声明的 Runtime 测试 | 前端静态资源、冻结 Solver、评测金标准 | 不改冻结 Solver，不直接调用外部服务绕过 Provider |
| 评测/安全 | `evaluation/**`、明确声明的 `scripts/*runtime*`、安全/评测文档和专属测试 | 生产 Runtime 实现、真实凭据和原始用户数据 | 不把真实密钥、原始 YAML 或学生隐私复制进评测资产 |

### 3.2 永久共享锁文件

以下路径经常同时影响多个角色，默认必须由主集成 Agent 为一个任务指定唯一写入者：

- `apps/api/app/services/task_runner.py`
- `apps/api/app/services/task_events.py`
- `apps/api/app/services/task_creation.py`
- `apps/api/app/models/entities.py`
- `apps/api/app/core/config.py`
- `.env.example`
- `apps/api/alembic/versions/**`
- OpenAPI/共享前端契约、公共类型和跨角色集成测试

数据库变更只能新增增量 migration；已提交 migration 不得修改。若 Runtime Agent 需要模型或配置变化，必须在声明中列出共享锁文件、migration 名称、升级/回滚方式和受影响的兼容测试。未经主集成 Agent 明确批准，其他角色只能提出补丁，不能并行落盘。

### 3.3 文件锁操作

开始工作前必须发送任务声明并获得确认。声明一旦发布，其他 Agent 不得修改其 `write_scope`，也不得在同一文件上“顺手修小问题”。发现必须跨范围修改时：

1. 停止编辑；
2. 把原因、目标文件和预期契约变化发给主集成 Agent；
3. 由主集成 Agent 扩大原任务范围，或拆出新的串行任务；
4. 重新运行范围检查后才能继续。

## 4. 任务声明模板

每个并行 Agent 在开始前复制以下模板填写。没有声明的工作不进入共享分支。

```text
TASK-ID: RT-YYYYMMDD-短名
角色: integrator | frontend | runtime-backend | evaluation-security
负责人: <agent/process id>
分支/工作树: <branch or worktree path>
目标: <一个可验收的结果>

write_scope:
  - <精确文件或目录模式>
disjoint_write_set:
  - <本进程独占的精确文件或目录模式；不得与同波次其他任务重叠>
read_scope:
  - <依赖的接口/文件>
out_of_scope:
  - <明确不会修改的边界>

依赖:
  - <commit hash / TASK-ID / 已冻结契约>
接口影响: none | proposal | approved-change
数据/迁移: none | new migration <name>
Provider: not-run | mock-only | authorized-real-run
凭据来源: environment-only | none

实现要点:
  - <状态、事件、错误码或 UI 行为>
验证命令:
  - <可复制的 PowerShell 命令>
预期证据:
  - <测试数量/报告路径/静态检查结果>
停止条件:
  - <本任务遇到什么情况必须停工>
交付提交: <完成后填写 hash>
```

声明必须同时说明“不会修改什么”。例如，界面任务应写明“不修改任务执行器、Provider、migration 和 Runtime 状态机”；Runtime 任务应写明“不恢复退役 Solver、原始输入和真实凭据”。

`write_scope` 描述本任务允许触及的范围，`disjoint_write_set` 描述本进程在当前并行波次实际独占的范围；后者必须是其他并行任务范围的严格不相交集合。若两个声明有任何路径重叠，即使只是同一目录下的不同意图，也必须改为共享锁并串行执行。

## 5. 共享接口契约

任何角色都可以实现契约，但只有主集成 Agent 可以批准契约变化。接口变化必须先提交契约提案，再提交实现。

### 5.1 Task 创建与生命周期

- `POST /api/v1/tasks` 是兼容入口；创建阶段只校验、持久化和排队，必须保持非阻塞。
- 路由不得直接执行 Provider、RAG、工具或子 Agent；这些动作发生在后台执行器/Runtime handler。
- Task 仍是用户可见生命周期和兼容响应的边界；`AgentRun` 是 Runtime 计划、节点和恢复的权威状态。
- Runtime 成功、部分成功、等待输入、等待审批、暂停、失败和取消必须通过明确状态/错误码向 Task 传播；不得让外层 Task 把 Runtime 验证失败覆盖成 `completed`。
- 任何 legacy fallback 必须显式记录模式、原因、Runtime 状态和是否绕过了 Runtime，不能静默降级。

### 5.2 Runtime Run、计划与节点

每次真实 Runtime 执行都必须能关联以下信息：

```text
run_id
task_id
agent_id + agent_version
runtime_plan_version
goal: objective / constraints / success_criteria
plan: ordered nodes + dependencies + iteration
node: node_id / handler_id / attempt / execution_key / status
observation: facts / evidence_ids / artifact_ids / warnings / reason_code
decision: execute | replan | ask_user | request_approval | finish | fail
checkpoint: state_version / sequence / event_sequence
```

要求：

- 节点输入输出必须是结构化、可校验、可脱敏的合同；不把隐藏思维链当作持久化状态。
- handler 只能调用已注册且具备输入 schema、权限、预算、超时、重试和结果 schema 的能力。
- `execution_key` 必须支持幂等；恢复时不得无证据重复执行不可重放副作用。
- 验证不足时优先产生结构化 `reason_code` 和 `replan`/`ask_user`/`fail` 决策，而不是补写一段未经验证的答案。
- checkpoint 必须足以恢复计划版本、节点状态、控制请求、证据引用和预算；不得依赖进程内隐式变量。

版本身份必须区分：`runtime_plan_version` 标识本次计划/Runtime 合同，
`agent_version` 标识待发布的 Agent artifact。前者存在不代表后者存在；
不能从 canary artifact、测试 fixture 或 synthetic payload 反推缺失的
`agent_version`。LearningLoop 的当前 readiness 投影会显式返回两个字段和
`canary_release_eligible`/`canary_reason`；两个真实 LearningLoop descriptor
已显式声明 `agent_version=learning-agent-v1`，但尚无 `authorized_paired`
evidence 时仍必须保持 fail-closed。readiness、Mock、synthetic contract 测试
和 provider-free preflight 都不是“已授权”证据。

### 5.3 Task/SSE 事件

- Task/SSE 是现有客户端兼容边界；Runtime 事件通过事件桥接进入同一事件存储和 SSE 通道。
- 同一 Task 的事件 `sequence` 必须单调递增且持久化；并发写入必须处理唯一键竞争，不能靠内存计数器。
- `Last-Event-ID` 重连只返回该序列之后的事件；重复消费不得重复产生业务副作用。
- 事件至少区分 `node_started`、`node_completed`、`node_retrying`、`node_failed`、等待/审批、checkpoint 和终态；事件 payload 只放脱敏摘要及引用 ID。
- 前端不能自行重排事件或推断缺失状态；遇到序号间隙必须重新拉取任务/事件状态并显示恢复中。

### 5.4 Provider、工具和子 Agent

- Provider 只负责外部调用和协议解析；Runtime 负责何时调用、调用几次、预算、超时、失败传播和是否重规划。
- 所有凭据、连接串和授权头只能来自受控环境变量/密钥系统；不得写入代码、YAML、测试 fixture、日志、截图、trace 或前端响应。
- 未配置或不满足 readiness 的 Agent 必须 fail-closed；Mock 结果必须明确标记为 mock/local。
- 新增 Agent 必须复用 Local Runtime、ModelService 和统一 Provider 边界，不创建旁路 HTTP client，不硬编码凭据。
- 子 Agent 必须有深度、预算、父子 Run 关系和结果 schema；不能通过任意 Python、URL 或未注册 handler 执行。

### 5.5 专业求解边界

- `ACADEMIC_PROBLEM_SOLVER` 是当前专业求解入口；退役 CT 专用 Solver 不属于活动执行面。
- 历史基线原始输入只允许出现在 `.local_inputs/`，不得进入公共仓库、评测 artifact、日志或截图。
- 任何涉及 Solver 的任务都必须附带 freeze 检查；若 hash、字段映射、文字/单图片工作流或 Provider 链发生意外变化，立即停止并回滚该任务。
- “通过 Mock”不能证明冻结 Solver 的历史等价性，也不能替代真实模型质量验收。

## 6. 消息与状态同步

### 6.1 状态板

每个任务至少同步以下状态之一：

`claimed` → `in_progress` → `ready_for_review` → `validated` → `integrated`
异常分支：`blocked`、`needs_contract`、`stopped`、`reverted`

状态消息使用固定格式：

```text
[TASK-ID][状态] 当前结果；已写文件；下一步；阻塞/风险；最新 commit
```

长任务至少在以下时点同步：开始、发现接口变化、首次失败、验证完成、提交完成、可合并。超过 30 分钟没有可见进展时，主集成 Agent 应主动检查，不让其他进程重复接管同一范围。

### 6.2 依赖与消息顺序

依赖任务必须先交付“契约摘要 + commit hash + 验证命令”，再通知下游。下游不得只依赖自然语言描述或未提交工作树。

推荐顺序：

1. 主集成 Agent 发布任务声明和共享契约；
2. Runtime 后端、前端、评测/安全在互斥范围内并行；
3. 各自完成局部验证并提交；
4. 主集成 Agent 按契约依赖顺序 cherry-pick；
5. 运行跨角色验证矩阵；
6. 评测/安全 Agent 复核发布门禁；
7. 主集成 Agent 决定 canary、default、继续观察或回滚。

### 6.3 标准协作示例

以下示例是推荐的最小协作链，适用于新 Runtime 能力接入：

```text
主进程定义接口
  → 发布 Goal/Plan/Node、状态、事件、错误码和版本字段契约
  → 后端先提交契约
  → Runtime 后端实现 handler/adapter，并先提交 schema、状态迁移和契约测试
  → 前端消费契约
  → 前端只依据已提交的契约渲染状态、SSE 事件和审批/恢复操作
  → 主进程集成回归
  → cherry-pick 后运行 Task 非阻塞、Runtime、SSE、Provider 和安全矩阵
```

执行约束：

- 主进程先发布 `TASK-ID`、接口版本和所有进程的 `disjoint_write_set`，未发布前不得并行编辑。
- 后端提交必须先包含可供消费的契约和失败语义；不能让前端通过猜测字段或读取后端内部实现推进。
- 前端只能消费已提交版本；发现字段不足时提出契约变更，不在浏览器中复制后端推理或 fallback。
- 主进程集成回归必须验证后端契约测试、前端消费、Task/SSE 兼容性和安全门禁的交叉结果；任一项失败都回到对应负责人，不通过删减断言解决。
- 该示例中的四个阶段可以由不同进程执行，但每个阶段都必须保留独立 commit、声明范围和验证证据。

## 7. 分支、提交与合并

### 7.1 分支和工作树

- 每个 Agent 使用独立分支或独立 worktree；分支名建议为 `codex/<role>-<task-id>`。
- 不在主集成分支上直接开发；不在他人工作树中修冲突。
- 开始前执行 `git status --short --branch`，记录既有未跟踪文件；本项目的 `experiment_demo.csv` 属于用户资产，任何任务都不得触碰、暂存或删除。

### 7.2 提交规则

提交前必须执行：

```powershell
git diff --check
git status --short
git diff --name-only <base-commit>...HEAD
```

结果必须证明：

- 只包含 `write_scope` 中的文件；
- 没有密钥、Bearer、历史原始输入、学生隐私或绝对本机路径；
- 没有修改已提交 migration、冻结 Solver 或无关格式；
- commit message 使用 `<scope>: <imperative summary>`，例如 `fix(runtime): preserve failed verification state`；
- 一个提交只对应一个任务目的，避免把格式化、重命名和功能混在一起。

### 7.3 cherry-pick 和合并顺序

主集成 Agent 只 cherry-pick 已报告 hash 且局部验证通过的提交：

```powershell
git cherry-pick <commit-hash>
git diff --check
# 按验证矩阵运行测试
```

若提交依赖另一个提交，必须按依赖顺序合并，并在任务消息中列出依赖 hash。合并后如果跨角色测试失败，主集成 Agent 不应直接删除失败断言或降低门禁；应标记 `needs_contract`，回到负责该边界的 Agent 处理。

只有在所有局部和跨角色验证通过后才能合并到长期分支。不得 force push、自动合并 PR 或在未审计的情况下 squash 掉导致问题定位所需的提交信息。

## 8. 验证矩阵

验证分为局部、跨边界和发布三层。命令中的路径必须替换为任务声明的精确集合，不得因方便改成全仓库写操作。

| 层级 | 负责人 | 必查内容 | 最低证据 |
|---|---|---|---|
| 路径/敏感信息 | 所有 Agent，主集成复核 | `write_scope`、未跟踪文件、凭据和原始输入隔离 | `git status`、`git diff --check`、敏感文件扫描 |
| 前端局部 | 前端 | 页面加载、状态映射、SSE 重连、脱敏渲染、控制操作 | 对应浏览器/Node 检查和前端测试 |
| Runtime 局部 | Runtime 后端 | 状态迁移、handler schema、预算、重试、幂等、checkpoint、恢复、失败传播 | 目标 Pytest、Ruff、Mypy |
| 评测/安全局部 | 评测/安全 | replay、semantic evidence、提示注入、权限、路径和凭据边界 | 离线评测报告、负向测试、扫描结果 |
| Task/SSE 边界 | 主集成 + Runtime | 创建非阻塞、事件顺序、并发序列、Last-Event-ID 重连、终态一致 | Task/SSE 回归测试 |
| Provider 边界 | 主集成 + 评测/安全 | 未配置 fail-closed、mock/real 标记、调用次数、超时和错误传播 | Provider contract/mock 测试；真实调用须有授权记录 |
| SOLVER 冻结 | 评测/安全 | 文件 hash、字段映射、文字/单图 parity、无原始 YAML 泄露 | freeze/parity 检查和报告 |
| 集成发布 | 主集成 | 角色间契约、全量受影响测试、配置检查、回滚点 | 合并 commit、命令输出、发布结论 |

PowerShell 基线命令如下；实际任务必须补上精确测试文件：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q <target-tests> --no-cov --basetemp .pytest-tmp-<task-id>
& .\.venv\Scripts\python.exe -m ruff check <changed-python-files>
& .\.venv\Scripts\python.exe -m mypy <changed-production-files>
git diff --check
```

前端任务至少运行对应 JavaScript 的 `node --check`（若文件是 JavaScript）和既有页面/契约测试。跨 Runtime 变更必须覆盖 Task 创建非阻塞、Runtime handoff、SSE 顺序与重连；事件协议变化必须增加或更新顺序/重连测试。Docker、真实 Provider 或外部服务未执行时，报告中必须明确写“未执行”。

## 9. 冲突处理

### 9.1 发现文件冲突

任何 Agent 发现目标文件已被他人修改，必须停止写入并报告：

```text
[CONFLICT][TASK-ID]
文件: <path>
冲突类型: overlapping-write | contract-drift | migration | test-expectation
已观察证据: <git diff/status/测试>
建议: split | serialize | rebase-after-commit | contract-review
```

不得用 `git checkout --`、`git reset --hard` 或删除他人改动解决冲突。主集成 Agent 根据以下顺序处理：

1. 能拆成不相交文件时拆分；
2. 不能拆分时按依赖串行化，并撤销一个写入锁；
3. 接口语义冲突时先冻结双方实现，更新契约提案；
4. migration 或冻结 Solver 冲突时直接停止，进行人工审查；
5. 合并后重新运行受影响矩阵，不能仅凭冲突标记消失就视为解决。

### 9.2 测试与实现不一致

测试失败分为三类：

- **实现回归**：保留测试，修复实现；
- **契约变更**：先更新共享契约和评测预期，再修改测试；
- **旧测试暴露真实边界**：不得弱化生产验证；应让失败以结构化状态、错误码或 fail-closed 方式显式呈现。

“把失败断言改成成功”不是冲突解决方案。

## 10. 停止条件与升级路径

出现任一条件，当前 Agent 必须停止修改并升级给主集成 Agent：

- 需要恢复退役 CT 专用 Solver 或其历史来源；
- 发现真实 API key、Bearer token、历史原始输入或学生隐私进入代码、日志、fixture、trace、artifact 或文档；
- 任务创建路径将直接执行 Provider、工具、RAG 或子 Agent，可能破坏非阻塞约束；
- 要绕过 Task/SSE/Provider 边界、绕过 Agent readiness 或把未发布 Agent 当作可执行；
- 需要修改已提交 migration，或无法同时提供增量 migration、升级和回滚证据；
- Runtime 失败/部分验证被外层提交成成功，或 legacy fallback 没有可观测原因；
- checkpoint 不足以恢复、执行键不幂等、重连会丢事件或重复副作用；
- 局部测试失败原因不明、验证命令无法复现、或只能通过放宽门禁来“通过”；
- 发现另一 Agent 正在写同一文件，或任务范围需要扩大到未声明路径；
- 真实 Provider、Docker、网络或外部授权是必要条件但当前未获明确授权。

升级消息必须包含复现命令、最小日志/trace 摘要、受影响的 `TASK-ID`、最后一个安全 commit 和建议的下一步。停止不等于失败；在证据完整前不得继续扩大改动面。

## 11. 推荐并行波次

### Wave 0：契约和锁

主集成 Agent 发布任务声明，冻结本轮 Agent/Plan/Node/SSE/审批字段、默认 launch mode、验证矩阵和合并顺序。评测/安全 Agent 先建立当前基线，确认没有现成回归。

### Wave 1：互斥实现

- 前端 Agent：只做 Runtime 状态、事件和控制操作的展示/交互；
- Runtime 后端 Agent：只做 Runtime handler、checkpoint、恢复和 Task handoff；
- 评测/安全 Agent：只做离线 case、semantic evidence、负向测试和安全报告。

三者不得互相修改默认范围；需要共享文件时转为串行任务。

### Wave 2：集成回归

主集成 Agent 按“契约 → 后端 → 前端 → 评测资产”顺序 cherry-pick，运行 Task/SSE/Provider/SOLVER 冻结矩阵。任何失败先分类，不直接改测试期待值。

### Wave 3：受控发布

先保持 shadow/canary；只有 Agent readiness、结构化回归和 semantic evidence 均满足 release gate，且有明确回滚配置时，才允许扩大流量。未获授权的真实 Provider 仍保持关闭，不能用本地 Mock 代替真实资格证据。LearningLoop 当前已由 capability descriptor 显式声明 `agent_version=learning-agent-v1`；仍必须检查该版本与 `runtime_plan_version` 是否和 authorized evidence 完整绑定，仅有 readiness 投影不够。

### Wave 3A：能力盘点与证据分层

能力盘点 Agent 只维护架构/评测文档中的事实矩阵，不修改 Runtime 实现、Provider、数据库或冻结基线。每一项能力必须分开记录：

1. **实现**：可定位的 service/adapter/plan/node/API 代码；
2. **可评测**：可重复的 provider-free、结构合同或离线 intake/preflight 测试；
3. **已授权**：真实、脱敏、同输入的 `authorized_paired` Legacy/Runtime trace，加上版本绑定的 semantic sidecar 和独立发布审批。

文档更新前先读取当前代码和测试，提交中只能包含任务声明的 docs write set。能力盘点不得把测试中显式注入的版本、`RuntimeCanaryEvidence(kind="synthetic")`、Mock/local 结果或 readiness 字段写成真实发布证据。缺少证据时写出具体 blocker、来源路径和下一门槛，并保持 Legacy/blocked 结论。

## 12. 完成定义（Definition of Done）

一个并行任务只有满足以下条件才可标记 `validated`：

- 目标、文件范围、依赖和停止条件已声明；
- 实现只修改声明范围，未触碰 `experiment_demo.csv` 和冻结/敏感资产；
- 局部测试、Ruff、Mypy 或适用的前端检查均有实际输出；
- 事件、状态、错误和 fallback 行为符合共享契约；
- 变更影响 Task 非阻塞、SSE 顺序/重连、Provider 授权和 checkpoint 恢复时，相关边界测试已覆盖；
- commit hash、验证命令、未执行项目和剩余风险已回报。

一个版本只有满足以下条件才可标记 `integrated`：

- 所有依赖提交已按顺序合并，工作区没有未声明的改动；
- 跨角色验证矩阵通过，失败项有明确 blocked/stopped 结论；
- 评测/安全 Agent 独立确认没有凭据泄露、冻结 Solver 变化、静默 fallback 或虚假成功；
- canary/default 决策、配置、回滚点和证据位置已记录；
- 未执行的 Docker、真实 Provider、外部授权和真实用户评测没有被描述为已完成。
- 能力盘点文档中的“已授权”列有对应的真实 evidence 路径和审批记录；仅有 readiness、Mock、synthetic 或离线 preflight 时，必须标记为“未授权/待补证据”。

## 13. 最小交付报告模板

```text
TASK-ID / commit:
变更文件:
完成内容:
契约影响:
验证命令与结果:
未执行项目:
安全/冻结检查:
剩余风险:
建议下一任务:
```

主集成 Agent 只有在收到上述报告、确认范围干净并完成跨角色验证后，才可以把任务从 `validated` 推进到 `integrated`。
