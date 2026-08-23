# 芯智导学六大演示案例优化总计划

## 总目标
围绕六个固定演示案例，完成一次“演示质量专项优化”：
1. 教师智能备课
2. 作业批改与首错诊断
3. 学生个性化学习路径
4. 科研前沿证据简报
5. 学院知识库治理
6. 模拟电子技术电路诊断

本阶段重点解决：
- 前端结果展示层次不清；
- 主界面中英文混杂；
- LaTeX 对积分、微分、矩阵、求和、联立方程等支持不完备；
- 六个案例没有把 Planner / Skill / RAG / Tool / Verification / Human Review 的差异化价值充分展示出来。

## 六案例统一展示链
用户任务 → 任务理解 → 制定计划 → 调用能力 → 证据/状态 → 验证/复核 → 最终结果

前端只展示“可审计执行轨迹”，不得展示模型私有推理链。

## 六案例能力定位
- 智能备课：Planner + RAG + Teaching Skill
- 首错诊断：Verification + Failure Attribution + Learning Loop
- 学习路径：Learning State + Experience + Planner
- 科研简报：Search/RAG + Evidence Governance
- 知识治理：Version/Permission/Governance
- 模电诊断：Vision + Solver + Tool + Verification

## Git
本阶段作为一个整体大阶段，内部不逐任务 commit。
全部完成后统一：
`git commit -m "feat(demo): optimize six flagship agent scenarios"`
然后 push + GitHub Actions。
