# P8：Release / Team Handoff / Showcase

## 交付文档
- README
- 快速启动
- 开发者导航
- 六案例运行手册
- 故障排查
- Pilot 真实测试报告
- 架构图
- Known limitations
- Rollback

## 挑战杯展示材料
整理：
- 系统总体架构
- 六案例能力矩阵
- Planner/Skill/Runtime 工作流
- Before/After Benchmark
- Pilot 真实反馈
- 典型失败与优化
- 安全与人工复核
- Demo 截图

## 最终报告
- `docs/release/phase_p_final_report.md`
- `docs/release/pilot_validation_report.md`
- `docs/release/team_handoff.md`
- `docs/demo/final_demo_runbook.md`

## Git
```text
git diff --check
frontend checks
backend tests
pilot regression
full suite
CI

git add <Phase P files only>
git commit -m "release: complete phase P pilot validation and hardening"
git push
```

不自动 merge main，不自动部署生产。
