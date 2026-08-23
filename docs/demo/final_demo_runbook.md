# 六案例最终演示运行手册

> 版本：Phase P RC；案例 ID、输入和复核边界固定。演示只展示可审计任务链，不展示模型私有推理。

## 统一启动

```powershell
cd C:\Users\86184\Desktop\xinzhi-daoxue
.\.venv\Scripts\python.exe scripts\validate_scenarios.py
.\.venv\Scripts\python.exe scripts\validate_planner_controlled_takeover.py
cd apps\web
npm run typecheck
npm run math:check
npm run demo:check
npm run smoke
npm run build
```

工作台：`http://localhost:8000/workspace?demo=1`。真实 Provider、外部检索和图片上传必须使用已授权的独立环境；普通回归不得继承开发者密钥。

## 案例矩阵

| ID | 黄金案例 | 备用案例 | 边界案例 | 失败/降级案例 | 主要观察点 |
| --- | --- | --- | --- | --- | --- |
| TP-01 | 反馈放大器 90 分钟备课 | BJT 共射 45 分钟翻转课堂 | 缺课程版本/评价标准 | 课程资料为空 | 目标、时间、活动、评价、教师确认 |
| FE-01 | 作业首错诊断 | CMOS 静态/动态功耗首错 | 缺标准答案或学生步骤 | 资料不足 | 首错、错误传播、验证任务、不自动定分 |
| LP-01 | 历史成绩驱动学习路径 | 四周电源训练 | 只有一次低分/无前测 | 课程证据不足 | 证据/推测分离、复测、教师介入 |
| RB-01 | 受时间窗约束的科研简报 | 视觉基础模型近 12 个月检索 | 无可靠来源/主题冲突 | 外部检索不可用 | 来源、时间窗、引用和不可发布边界 |
| KG-01 | 2026 资料替代 2025 资料审查 | 课程资产 OCR 复核 | 来源不明/含教师备注 | 权限或审批不满足 | 版本、权限、回滚、人工审批 |
| AC-01 | 运放负反馈题图诊断 | 清晰/模糊/饱和边界图 | 拓扑或参数不清 | 视觉验收失败 | 图像事实、方法、公式、拒答与复核 |

## 1. TP-01 教师智能备课

黄金输入：为反馈放大器设计一节 90 分钟课堂，给出教学目标、课堂流程、例题、分层练习和形成性评价，并标出课程版本或基础假设的教师确认点。

预期链路：`GoalContract → teaching.lesson_design → course evidence → draft → teacher review`。

不要把通用建议显示为课程正式标准；总时长、核心段时长、目标—活动—评价闭环必须可见。

## 2. FE-01 作业首错诊断

黄金输入：提交电路题分步解答，要求定位最早实质错误，说明错误传播，并给出不直接替学生做完的验证任务。

预期链路：`GoalContract → teaching.assignment_review → first-error verification → feedback`。

演示时确认没有自动总分；学生没有提供足够步骤时，结果必须进入待补充/待复核边界。

## 3. LP-01 学生个性化学习路径

黄金输入：卷积 3/5、傅里叶级数 4/5、傅里叶变换 2/5、采样 1/4、拉普拉斯 4/4，要求安排优先级、先修关系、验证任务和下一次复测。

预期链路：`GoalContract → learning.path_plan → learning state/evidence → staged plan → re-test`。

结果不能宣称“已经掌握”或仅凭一次分数定性；证据不足时保留人工介入点。

## 4. RB-01 科研前沿证据简报

黄金输入：限定 2025-01 至 2026-08 的医学影像基础模型用于肺结节分割研究，整理问题、方法、来源和局限；没有可靠来源的定量结论不要补写。

预期链路：`GoalContract → research.evidence_brief → bounded retrieval → source review → brief`。

外部 Provider 未配置时必须明确不可用/待检索，不得用 Mock 结果冒充科研证据。

## 5. KG-01 学院知识库治理

黄金输入：审查 2026 版替代 2025 版的课程资料更新，识别来源不明、教师备注、权限、发布前检查和回滚关系。

预期链路：`GoalContract → knowledge.govern → version/permission audit → approval boundary`。

系统可以给出治理建议，但不能自动发布未经教师/管理员确认的课程资产。

## 6. AC-01 模拟电路题图诊断

黄金输入：从左侧案例卡加载运放图，要求先判断线性负反馈，再说明虚短/虚断适用条件、节点关系、输出饱和边界和读图不确定性。

预期链路：`GoalContract → vision.circuit_parse → academic.solve → method/tool verification → review`。

图片地址固定为 `/demo-assets/case6-opamp.png`；前端预览走公共演示资产，真实用户上传仍走 `/api/v1/files`。图像字段不清时必须拒答或待补充，不得补猜拓扑和参数。

## 结果记录模板

```text
record_id:
scenario_id:
task_id:
provider / model:
mock_used:
planner capability:
selected skills:
retrieval / tool / reflection:
task status:
evidence status:
publishable:
manual review required:
SSE sequence:
user score (1-5):
failure code:
```

每次演示结束后保存 task、事件、结果和截图；不要为了得到满意答案反复重试并覆盖原始证据。
