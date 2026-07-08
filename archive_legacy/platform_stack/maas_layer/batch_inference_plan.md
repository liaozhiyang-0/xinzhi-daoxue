# 批量推理计划

## 1. 目标

批量推理用于验证识图解题 Prompt 和课程问答 Prompt 在一组固定样例上的稳定性。第一阶段只做离线评估，不接入真实学生数据。

## 2. 输入数据

建议字段：

```json
{
  "case_id": "VS-CT-001",
  "course": "电路理论",
  "chapter": "第8章 一阶电路的暂态分析",
  "image_path": "assets/demo_cases/vs_ct_001.png",
  "text_hint": "求 t>=0 时电容电压",
  "expected_method": "三要素法"
}
```

## 3. 输出数据

保存模型输出、结构化电路结果、关键方程、最终答案和评估结果，便于人工复核。

```text
outputs/
├── raw_model_outputs/
├── normalized_solutions/
└── evaluation_results/
```

## 4. 执行流程

1. 准备图文样例；
2. 调用识图解题 Prompt；
3. 保存原始输出；
4. 调用评估 Prompt 或人工评分；
5. 汇总错误类型；
6. 更新 Prompt 和样例标注。

## 5. 注意事项

- 不上传真实学生隐私数据；
- 不把看不清的样例作为模型能力失败，需单独记录图片质量问题；
- 每次 Prompt 修改后保留版本号，便于对比。

