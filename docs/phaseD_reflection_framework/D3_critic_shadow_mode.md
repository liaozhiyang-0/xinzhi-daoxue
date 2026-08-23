# Phase D3：Critic Shadow Mode

## 目标
Critic 先旁路运行，只观察和评分，不修改真实答案。

## 路径
```text
Draft Result ─────────→ Existing Verification → Publish
     |
     └→ ReflectionPolicy → Critic → CriticTrace ONLY
```

## 必须完成
- Critic 使用统一 contract；
- 只读取 goal、canonical plan、draft、evidence refs、tool observations、必要 trace；
- 输出只进入 trace/evaluation；
- Critic failure 不影响真实任务；
- 记录 issue/severity/evidence/pass-revise-fail/latency/token/cost；
- 与 deterministic/domain verification 做 disagreement 对照。

## 首批场景
Academic Solver、Knowledge QA、Research；Teaching 可先 shadow。

## 关键统计
verifier fail + critic pass、verifier pass + critic revise/fail、unsupported critique、真实失败发现率、schema 重复检查比例。

## 禁止
不修改答案、不 revision、不写 Experience Memory、不扩大 Planner/Skill canary。

## 提交
本阶段不 commit，完成后继续 D4。
