# P4 CT/AE 课程资产审计起点

## 审计结论

本阶段先做只读审计和可追踪指标，不自动编写三个演示案例，也不修改冻结的 `SOLVER_CT v1.0`/`SOLVER_CT_V1`。

- 知识库清单包含 CT 1,099 条、AE 625 条、DE 575 条、SS 459 条、DSP 279 条和 COMM 381 条记录。
- 当前质量问题清单共 150 条：CT 31 条、AE 30 条；CT 主要是未解析二进制/归档资料，AE 主要是未解析二进制和临时/草稿资料。
- CT、AE、DE 各有 10 个技能定义；错误池分别有 4、3、3 个已启用且教师复核的精确模板。
- 技能定义共引用 23 个错因签名，当前模板覆盖 10 个；CT 缺 4 个、AE 缺 6 个、DE 缺 6 个。
- 运行时 Course Registry 已有 CT、AE、DE 课程包，但 `agent_configs/course_packs/` 目前只有 CT 的兼容 YAML。AE 课程包运行时状态为 `basic`，不应在材料补齐前宣称完整竞赛能力。

## 本阶段改动

`scripts/validate_config.py` 现在额外输出：

- 每门课技能引用的错因签名数量、可用模板覆盖数量、覆盖率和未覆盖签名。
- 每门课运行时 CoursePack 的实现状态、问题类型数、校验规则数和兼容 YAML 是否存在。

另外新增只读命令 `scripts/audit_course_assets.py`，把课程配置、知识库质量问题、评测案例数量和竞赛支撑边界合并成一个 JSON 报告；它也会检查 `submission/contest_package/` 材料骨架是否存在。默认只输出到终端，不修改仓库；只有显式传入 `--output` 时才写入指定文件。

这些指标只反映仓库配置覆盖情况，不代表模型准确率、学习效果或竞赛成绩。

当前未覆盖的 CT/AE 错误签名已另存为 `config/error_pool/proposals/` 中的禁用候选，审计会报告其覆盖缺口但不会把它们计入运行时覆盖率；候选模板的教师复核流程见 `docs/implementation/p8_ct_ae_error_templates.md`。

CT/AE 的 `config/course_assets/*.yaml` 是仅供审计和竞赛证据使用的兼容清单，运行时仍以 `apps/api/app/courses/registry.py` 为唯一 CoursePack 来源；它不复制 Solver 图，也不触发 Provider。

CI 也会执行 `audit_course_assets.py`，因此课程配置、知识库质量和材料骨架的证据边界会随代码变更持续检查。

## 后续顺序

1. 先由教师/项目负责人审核 CT、AE 缺失错因签名的优先级和教学表述。
2. 仅对已确认的错因补充 `teacher_reviewed: true`、`enabled: true` 的精确模板，并增加针对性测试。
3. 再评估是否需要 AE CoursePack 兼容 YAML；若新增，必须以运行时 Course Registry 为唯一事实源，不能复制 Solver 实现。
4. 最后再把已审核课程资产接入教师工作台和竞赛材料目录；演示案例仍由用户单独设计。

验证命令：

```powershell
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\audit_course_assets.py --course CT --course AE
.\.venv\Scripts\pytest.exe apps/api/tests/test_config_validation.py apps/api/tests/test_error_pool.py -q
```
