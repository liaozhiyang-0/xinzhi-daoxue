# Codex 六大演示案例专项优化执行指令

执行六个固定演示场景的专项优化，同时完成前端显示、中文一致性和 LaTeX 渲染治理。

## 顺序
前端统一规范 → 中文治理 → LaTeX → 智能备课 → 首错诊断 → 学习路径 → 科研简报 → 知识治理 → 模电诊断 → 跨案例回归。

## 前端
- 主界面统一中文；
- 建立六场景 Demo 卡片；
- 增加“智能体执行”轨迹；
- 技术 ID、raw JSON、Provider 错误放高级详情；
- 不显示私有 chain-of-thought；
- Demo mode 必须运行真实 Agent。

## LaTeX
优先复用现有 renderer；若不完整，可统一采用 React Markdown + math pipeline。
支持积分、微分、矩阵、cases、aligned、sum、phasor、complex、units。
公式失败不得导致消息崩溃。

## 后端
仅在必要时调整 structured result / presentation adapter。
禁止：
- 新 public Agent
- 第二 Runtime
- Demo 特例硬编码进通用 Runtime
- 为测试案例硬编码答案
- 改 Planner/Skill/Reflection/Experience owner

## 测试
把各文档示例尽量转为自动/半自动 fixture。
重点检查：
中文、LaTeX、progress、evidence/review、incomplete input、degraded result、无虚构 DOI、无自动发布、无自动定总分、无编造图像事实。

## Git
整个阶段完成后统一：
`git commit -m "feat(demo): optimize six flagship agent scenarios"`
然后 push + CI，不自动 merge main。

## 最终文档
- `docs/demo/six_scenario_demo_guide.md`
- `docs/demo/six_scenario_test_report.md`
- `docs/demo/frontend_display_standard.md`
- `docs/demo/math_rendering_audit.md`
