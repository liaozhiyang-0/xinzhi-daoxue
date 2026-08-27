# 六大 Agent 演示案例测试报告

## 1. 测试范围

本报告覆盖：

- 六案例前端注册、展示和输入契约；
- 任务状态、执行轨迹和结构化结果展示；
- 图片材料导入和题库图片服务；
- LaTeX 公式渲染夹具；
- 真实模型调用下的案例 6 图像任务边界。

## 2. 本地验证命令

```powershell
cd apps/web
npm run typecheck
npm run math:check
npm run demo:check
npm run smoke
npm run build

cd ../..
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_unified_web_ui.py::test_workspace_shows_six_showcase_examples `
  apps/api/tests/test_unified_web_ui.py::test_local_analog_question_image_is_served_from_the_question_bank `
  apps/api/tests/test_showcase_case_matrix.py `
  --disable-warnings -q
```

已执行结果：

| 检查 | 结果 |
| --- | --- |
| TypeScript typecheck | PASS |
| 公式夹具 | PASS，31 条 |
| 六案例契约 | PASS，6 个真实案例条目 |
| Web smoke | PASS |
| React production build | PASS；Vite 仅提示 KaTeX 造成的 chunk 较大警告 |
| 图片/六案例后端回归 | PASS，17 passed |
| 触及文件的 `git diff --check` | PASS；仅有 Git 的 LF/CRLF 提示 |

工作树全量 pytest 结果为 `1938 passed, 5 failed, 15 skipped`。这次全量结果混入了阶段外的既有未提交改动，5 条失败均不是案例 6 图片导入失败：商业场景覆盖/数量断言 2 条、外部来源数量断言 1 条、本地文本模型兼容测试 1 条、场景接口数量断言 1 条。它们分别反映当前工作树的场景目录和 RAG/来源注册表基线漂移；本阶段没有删除场景、关闭测试或降低 CI 标准。

## 3. 真实运行验证

### AC-01 图片解题

已通过真实服务链验证：

```text
浏览器选择 AC-01
→ 加载题库图片
→ POST /api/v1/files
→ 创建 solve_problem 任务
→ 真实视觉模型调用
→ 结构化结果与复核边界展示
```

上传文件实际被识别为 JPEG，大小为 17,640 bytes，任务进入完成状态。模型判断电路拓扑证据不足时，结果明确要求补充器件端点、节点连接、参数、极性和待求量，没有生成未经核验的电路结论。这是本案例预期的安全边界。

### TP-01 人工复核门

已验证任务可以经过检索和模型执行后进入 `waiting_review`。前端展示“等待人工复核”，不会把未获授权的结果误显示为最终完成结果。

## 4. 图片导入修复

案例 6 的导入问题有两个边界：

1. 案例展示图片不能依赖被忽略的本地题库缓存，也不能复用管理员专用题库接口；
2. 前端材料校验不能只依赖 MIME，因为部分浏览器或测试文件的 MIME 可能为空。

当前案例 6 使用 `/demo-assets/case6-opamp.png` 的仓库内演示资产；真实用户图片仍通过 `/api/v1/files` 上传。前端在 MIME 为空时允许 `.jpg/.jpeg/.png/.webp` 扩展名继续校验，同时仍保留 20MB 上限和原有文档类型白名单。后端图片服务和真实上传链均已通过验证。

## 5. 已知基线冲突

在较宽的既有回归集合中，以下 5 条失败属于工作树其他阶段的基线漂移，需单独治理：

- `test_commercial_scenario_cases.py::test_enabled_commercial_scenarios_are_synthetic_and_review_gated`：商业案例未覆盖当前启用目录中的两个场景；
- `test_commercial_scenario_preflight.py::test_enabled_commercial_cases_route_without_network_or_provider_calls`：旧断言期望 6 条，当前目录报告 8 条；
- `test_external_source_registry.py::test_external_source_registry_is_complete_and_manual_reviewed`：旧断言期望 6 条，当前注册表为 10 条；
- `test_embedding_compatibility.py::test_local_text_model_load_does_not_probe_the_network`：当前本地模型加载路径与测试中的 `SentenceTransformer` 替身不匹配；
- `test_unified_web_ui.py::test_demo_scenarios_and_presentation_mode_are_explicit`：旧断言要求场景接口返回 5 条，而当前目录实际返回 9 条。

本阶段没有通过删除场景或降低接口语义来迁就这些失败。案例 6 图片相关断言和六案例前端契约已经单独通过。

案例 6 图片相关断言已通过；上述 5/9 条属于既有测试基线清理项，应单独更新测试期望或明确接口过滤语义。

## 6. 验收判断

六案例的前端展示、图片导入、公式夹具和真实 AC-01 运行链已具备继续做内容优化的基础。当前剩余风险主要是：科研案例的外部证据质量、各案例真实输入样本的丰富度，以及旧场景数量断言的基线治理。
