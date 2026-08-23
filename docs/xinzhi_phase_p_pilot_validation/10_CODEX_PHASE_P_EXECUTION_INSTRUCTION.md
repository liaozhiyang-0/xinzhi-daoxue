# Codex Phase P 完整执行指令

执行“芯智导学 Phase P：Pilot Validation & Product Hardening”。

前提：
- Phase N 已完成；
- Planner + Capability + Skill + CanonicalPlan 已成为默认生产控制面；
- Pilot 0 已由组员完成真实测试并产生真实数据。

## 顺序
P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7 → P8

## 原则
1. 不再新增核心架构层。
2. 不恢复旧 Router / fixed Agent / legacy runtime。
3. 所有 Agent 优化必须来自 Pilot 证据。
4. 不为单个测试 case 硬编码。
5. 不修改 expected answer 迎合系统。
6. 不降低验证标准换通过率。
7. 六案例安全边界必须保留。
8. Phase M 的 React/中文/KaTeX 保持单一实现。
9. critical bug 优先于 answer-quality polish。
10. 每轮优化必须 replay + regression。

## P1
输出 Top 15 Failure Patterns，只选择 Top 5–8。

## P2
先关闭产品阻断 bug。

## P3
最多 2–3 轮，每轮 3–5 个真实高价值问题。

## P7
重新让真实用户 Final Pilot，不以开发者自测代替。

## Git
最终统一：
`git commit -m "release: complete phase P pilot validation and hardening"`
push + CI，不自动 merge main。

## 最终交付
- `docs/release/phase_p_final_report.md`
- `docs/release/pilot_validation_report.md`
- `docs/release/team_handoff.md`
- `docs/demo/final_demo_runbook.md`

完成后停止。
