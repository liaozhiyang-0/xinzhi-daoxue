# 01 本地题库与电路图资产发现

## 目标

用户本地已经有大量真实电路图与题目。本阶段必须优先利用真实资产进行多图、高难题、语义正确性和长对话测试。

## 只读扫描

优先从项目仓库及明确的测试、数据、知识库目录开始查找：

- png / jpg / jpeg / webp
- pdf
- md / txt / json / csv

优先目录关键词：

circuit, ct, circuit_theory, problem, question, exam, dataset, benchmark, fixture, knowledge, 教材, 题库, 电路, 试题, 答案。

不要无边界扫描整个系统盘。

## 原始数据保护

禁止：

- 移动；
- 删除；
- 改名；
- 覆盖；
- 批量复制。

允许建立轻量 manifest。

## 建议索引字段

```json
{
  "asset_id": "...",
  "path": "...",
  "type": "image|pdf|text|question",
  "course": "CT|AE|DE|SS|UNKNOWN",
  "possible_role": "problem_text|circuit|solution|waveform|option|unknown",
  "group_hint": "...",
  "source_dir": "...",
  "safe_for_test": true
}
```

## 自动分组

利用文件名前缀、相邻编号、同目录、题号、页码推断：

- 题干 + 电路
- 题目 + 答案
- 总图 + 局部图
- 连续两页
- 题目 + 电路 + 波形
- 图 A / 图 B

## 真实资产优先级

真实本地题库 > 项目已有 fixture > 已有 benchmark > 必要时人工构造。

## 输出

生成：

- `docs/audit/28_local_asset_inventory.md`
- `docs/audit/29_real_asset_test_manifest.md`

报告发现多少题、多少图片、多少可形成多图组、课程分布、多少具备答案/解析、多少可作为 Semantic Benchmark。
