# T6：Hidden Holdout 泛化测试

## 目标
测试系统是否真正泛化，而不是记住开发题。

## 数据划分
长期建议：
Development 50% / Regression 25% / Hidden Holdout 25%。

例如 800 cases：
400 development / 200 regression / 200 hidden。

## Hidden 原则
Codex 日常优化不得读取 hidden expected answer。
只在 major optimization / release candidate / milestone 时运行。

统计：
dev score、regression score、hidden score、generalization gap。

若 dev ↑ 但 hidden ↓，视为过拟合。

## 提交
`test(eval): establish hidden holdout benchmark`
