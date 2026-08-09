# 剩余五个商业案例总报告

日期：2026-08-07  
范围：`faculty_course_copilot_v1`、`assessment_diagnosis_v1`、`student_learning_path_v1`、`research_data_workbench_v1`、`department_knowledge_governance_v1`。科研前沿场景是已有完成基线，本轮只引用其工程边界，不将其计入新增五案。

## 1. 对比矩阵

评分为本地证据下的工作成熟度判断，不是市场调研结果，也不是准确率或比赛成绩。

| 案例 | 当前主 Agent/模式 | 商业价值 | 技术可行性 | 市场空间 | 竞争壁垒 | 演示效果 | 成熟度 | 最大风险 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 教师智能备课 | `TEACH_01...`；本地/Mock/fallback | 4 | 4 | 3 | 3 | 5 | 4 | 教师试点与课程资产授权不足 |
| 作业首错定位 | `TEACH_02...`；本地/Mock/fallback | 5 | 4 | 4 | 4 | 5 | 4 | 评分公平、隐私和首错一致性未实证 |
| 学情学习路径 | `LEARN_01_LOCAL...` | 4 | 4 | 4 | 3 | 4 | 4 | 学习成效与画像合规未实证 |
| 科研数据分析 | `RESEARCH_03...`；本地计划/解释 | 5 | 4 | 4 | 4 | 4 | 4 | 真实数据、方法责任和复现成本 |
| 学院知识治理 | `LEARN_01_KNOWLEDGE...`；当前安全 fallback | 5 | 3 | 4 | 5 | 4 | 3 | 正式治理 Agent 未发布，权限/版权试点不足 |

评分解释：5=工程边界、交付路径和演示均有本地证据且缺口明确；4=核心链路可演示但需要授权试点；3=主要价值成立但关键运行或市场证据仍缺。没有任何一项评分代表已获得客户、收入或外部市场份额。

## 2. 每案完成记录

### 教师智能备课

1. 名称/完成度：内容闭环完成；本地场景演示完成；真实教师试点待补。
2. 发现问题：原有材料只有场景契约和三步演示，没有完整客户/付费/竞争/答辩逻辑；市场和价格没有证据。
3. 修改文件：`docs/commercial_cases/faculty_course_copilot_v1.md`、`config/scenarios.yaml`、验证器、Demo 使用说明和证据矩阵。
4. 核心内容：目标对齐、课程 RAG、教师复核、MVP/试点/规模化、6个演示和10问10答。
5. 商业变化：从“教师工具”收敛为单课程工作台→课程群→院系空间的交付路径；价格保持待验证。
6. 技术/演示变化：6步演示；前端显示 Agent、价值闭环、预检和 Mock/fallback 状态；任务 202 非阻塞。
7. 证据：场景 YAML、Agent 注册表、本地执行适配、TaskRunner、场景证据策略和 preflight；外部市场/客户证据待补。
8. 测试：场景/商业案例/15项 API 回归；应用内浏览器真实 Mock 任务完成。
9. 需补信息：授权课程、教师复核、采购和竞品来源、真实成本。
10. 下一步：用1门授权 CT 课程完成3个教师样例和复核记录。

### 作业首错定位

1. 完成度：商业、技术、答辩、6演示完成；真实抽检待补。
2. 问题：容易把自动评分包装成产品，缺少“初审而非定分”边界和实际批次经济模型。
3. 修改文件：`docs/commercial_cases/assessment_diagnosis_v1.md`、场景配置、验证器、提交包材料。
4. 核心内容：首错、证据、分层提示、验证题、教师抽检和风险边界。
5. 商业变化：按批次/审核席位交付，先抽检再扩展题库/学情；不宣称准确率。
6. 技术/演示变化：6个演示覆盖首错、连锁错误、批次抽检和拒绝自动定分。
7. 证据：`TEACH_02` 输入/输出契约、错误池/评分规则配置、场景证据政策；教师一致性待补。
8. 测试：同统一场景验证；未执行真实学生作业试点。
9. 需补信息：授权作业、rubric、抽检记录、隐私与公平审查。
10. 下一步：用脱敏的三份作答做教师双人抽检，记录改判原因。

### 学情诊断与个性化学习路径

1. 完成度：产品/商业/演示闭环完成；学习成效待补。
2. 问题：需防止一次错误变成“能力判定”，且必须确保学生/课程/会话隔离。
3. 修改文件：`docs/commercial_cases/student_learning_path_v1.md`、场景配置、验证器、提交包材料。
4. 核心内容：作答证据→三步路径→复测→更新，付费方和隐私边界清晰。
5. 商业变化：按课程/活跃学生订阅，收入与学习增益都标待验证。
6. 技术/演示变化：覆盖复测、教师干预、跨主题隔离和拒绝能力判定。
7. 证据：学习场景契约、`LEARN_01_LOCAL` 能力、`workspace.js` 的 attempts/mastery/retests 展示；真实学习结果待补。
8. 测试：场景路由与 API 回归；未执行授权学生试用。
9. 需补信息：伦理审批、学生同意、学习评价设计、课程样本。
10. 下一步：先做教师可见、学生脱敏的单课复测试点。

### 科研数据分析与可复现解释

1. 完成度：商业逻辑、技术边界、6演示完成；真实研究任务待补。
2. 问题：无数据时容易被误解为“已完成分析”，需要明确 plan/insufficient_data/interpreted。
3. 修改文件：`docs/commercial_cases/research_data_workbench_v1.md`、场景配置、验证器、提交包材料。
4. 核心内容：数据质量、方法、可执行产物、解释限制和项目交付。
5. 商业变化：按研究任务/项目交付，扩展实验室和研发部门；价格与复现指标待补。
6. 技术/演示变化：无数据不出结论、方法选择、代码骨架和风险拒答演示。
7. 证据：`RESEARCH_03` 注册/contract、`DataAnalysisExplanation`、本地 formatter；真实数据授权和方法来源待补。
8. 测试：场景路由与 API 回归；未执行真实数据/工具执行。
9. 需补信息：数据字典/协议、方法参考、环境、研究者复现记录。
10. 下一步：选一个无敏感数据的小任务做同环境复现。

### 学院知识库治理与课程资产发布

1. 完成度：商业/治理/演示文档完成；运行时当前安全 fallback，正式 Agent 发布待补。
2. 问题：原场景绑定 `LEARN_01_KNOWLEDGE_QA_V1`，但未配置时会降级本地检索，前端需要把生产阻塞与演示可用分开。
3. 修改文件：`docs/commercial_cases/department_knowledge_governance_v1.md`、场景配置、验证器、提交包材料；未修改冻结基线。
4. 核心内容：资产清单、版本/来源/审查/发布/回滚、学院空间和权限审计。
5. 商业变化：按学院空间/资产治理服务交付，扩展校级和服务商生态。
6. 技术/演示变化：6步演示明确 fallback_only、人工审核和发布前验证。
7. 证据：场景证据 review API、知识治理来源类型、前端证据/状态组件；真实权限/版权审计待补。
8. 测试：preflight 明确 `demo_ready=true`、`production_ready=false`；API 回归通过。
9. 需补信息：学院资产授权、角色矩阵、发布审计、正式 Agent/Provider 发布记录。
10. 下一步：先完成单学院 CT 资产盘点和权限验收，再决定正式发布。

## 3. 推荐优先级

1. **作业首错定位**：商业痛点最直接，演示可在短时间内展示“证据—提示—教师决策”，适合挑战杯答辩，但必须先补教师抽检和公平/隐私材料。
2. **科研数据分析**：技术边界可信、可复现叙事强，适合科研型路演；最大缺口是真实数据和方法责任。
3. **教师智能备课**：最容易让评委理解，适合作为主推演示入口；需补课程授权和教师试点。
4. **学院知识治理**：治理壁垒和组织价值强，适合项目制/院系采购答辩；当前正式 Agent 与权限验证降低了演示成熟度。
5. **学情学习路径**：产品想象空间大，但学习成效、伦理和隐私证据要求最高，建议在完成单课复测后再主推。

主推组合建议：以“作业首错定位”作为商业价值主案例，以“科研数据分析”作为技术可信度副案例，以“教师智能备课”作为直观现场 Demo；知识治理作为学院级扩展路线，学习路径作为后续增长线。该建议基于当前本地工程证据，不是外部市场结论。

## 4. 统一风险与待补材料

- 外部市场规模、政策、竞品功能/份额、价格和客户采购预算：**待补证据**。
- 教师/学生/研究者授权试点、隐私/伦理审批、数据许可、人工复核记录：**待补**。
- 真实 Provider 发布与非 Mock 结果：**待补**；当前所有 Mock/fallback 均在前端和报告中显式标记。
- Playwright：本机 Node 依赖缺失，现有浏览器脚本未完成自动化子步骤；应用内浏览器已完成真实页面和 Mock 任务冒烟。
- Docker：本轮未执行，不能报告 Docker 通过。
- `SOLVER_CT v1.0`/`SOLVER_CT_V1`：本轮未修改。

## 5. 全部变更与验证命令

主要变更：

- `docs/commercial_cases/README.md`
- `docs/commercial_cases/faculty_course_copilot_v1.md`
- `docs/commercial_cases/assessment_diagnosis_v1.md`
- `docs/commercial_cases/student_learning_path_v1.md`
- `docs/commercial_cases/research_data_workbench_v1.md`
- `docs/commercial_cases/department_knowledge_governance_v1.md`
- `docs/commercial_cases/final_report.md`
- `config/scenarios.yaml`
- `scripts/validate_commercial_scenarios.py`
- `apps/api/tests/test_scenarios_api.py`
- `apps/api/app/static/debug/demo.js`
- `submission/contest_package/03_demo_user_guide.md`
- `submission/contest_package/06_validation_report.md`
- `submission/contest_package/09_evidence_matrix.md`
- `submission/contest_package/package_manifest.yaml`

验证：

```powershell
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe scripts\validate_commercial_scenarios.py
.venv\Scripts\python.exe scripts\validate_scenarios.py
.venv\Scripts\python.exe scripts\run_commercial_scenario_preflight.py
.venv\Scripts\python.exe -m pytest apps\api\tests\test_scenarios_api.py apps\api\tests\test_scenario_catalog.py apps\api\tests\test_scenario_preflight.py -q --no-cov
node scripts\run_web_ui_browser_acceptance.js
```

最后一条命令本轮只完成了静态页面/API preflight 19/19；因本机缺少 `playwright` Node 包，浏览器脚本子步骤未执行。应用内浏览器对 `/demo`、场景工作台、核心 JS/API 200 和一次备课 Mock 任务完成做了独立验证。
