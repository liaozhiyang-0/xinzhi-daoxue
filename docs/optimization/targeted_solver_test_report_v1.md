# 统一学术求解器定向测试报告 v1

## 1. 测试边界

本轮执行静态检查、单元测试、契约测试和不调用真实 Provider 的小规模定向
回归。没有运行完整 336 例，没有修改原题、标准答案、断言或评分阈值。

私有定向测试在本地读取：

- `curated_answer_sets/part2_error_detection.json`；
- `curated_answer_sets/part3_boundary.json`；
- `balanced_336/all_cases.json`；
- 全量历史报告 `full_live_20260727T120134Z/raw/latest.json`。

这些文件不存在时相关测试会明确 skip，公共 CI 不依赖私有题库内容。

## 2. 已执行测试

### 2.1 定向单元、契约与兼容回归

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_targeted_solver_optimization.py `
  apps/api/tests/test_universal_academic_solver.py `
  apps/api/tests/test_solution_packet_adapter.py `
  apps/api/tests/test_teaching_loop_phase2_services.py -q --no-cov
```

覆盖内容：

- 请求时间预算和截止阶段；
- simple/complex 规则分类和调用预算；
- `fallback_count` 限制与回退循环阻止；
- AE 分析模式、BJT/MOS 工作区、增益符号；
- DE 真值表等价与状态转移模拟；
- REVIEW 第一错误步骤和此前有效步骤；
- 六类边界拦截；
- 旧请求默认 SOLVE；
- 新指标默认值、JSON 解析、LaTeX 字符串和无 JSON 代码围栏；
- 统一求解器现有文本、多图、续写和异常降级兼容性；
- SolutionPacket 与教学核对兼容性。

结果：`66 passed`，2 条第三方弃用预警，耗时 2.86 秒。

### 2.2 私有固定错误审查案例

未修改原题和学生答案，固定选择：

```text
CUR-ERR-CT-001
CUR-ERR-AE-001
CUR-ERR-AE-002
CUR-ERR-DE-001
CUR-ERR-DE-002
CUR-ERR-SS-001
```

本地断言要求输出原案例指定的 `expected_first_error_step`。六例均由确定性规则
定位，不调用第二个大模型，也不把完整参考解作为学生反馈。

### 2.3 私有固定边界案例

固定选择：

```text
CUR-BND-CT-001
CUR-BND-CT-002
CUR-BND-AE-001
CUR-BND-AE-002
CUR-BND-DE-001
CUR-BND-DE-002
```

六例均在模型调用前被拦截，并返回 `conditional` 或 `unusable`、缺失信息或
不确定点。

### 2.4 历史超时案例

固定选择覆盖 CT、AE、DE、SS、DSP：

```text
CT-C01-Q01
KB-CT-11-13
AE-10-1-2
DE-3-2-11
SS-C03-Q05
KB-DSP-3-16
```

测试先核对它们在历史报告中均为约 180 秒 timeout，再用同一原始题目模拟主
模型超时。六例均保留本地 Graph 的受控结果，`partial_result_available=true`，
而不是返回空答案或让校验覆盖已有结果。

## 3. 定向性能变化

以下是本地确定性/Mock 回归结果，不是新的 336 例 live 指标：

| 项目 | 历史或旧行为 | 本轮定向结果 |
|---|---|---|
| 短多图完整回答 | 缺内部标记可能触发一次重复主生成 | 拼接 2 图保持 1 视觉 + 1 主生成，共 2 次 |
| 3 图逐图模式 | 可能在汇总后继续重复主生成 | 3 视觉 + 1 汇总 + 1 主生成，共 5 次 |
| 简单文本生成 | 可能进入统一二次校验 | 生成预算 1，默认不触发大模型校验 |
| 回退级联 | primary/fallback 与旧基线缺少统一账本 | 默认最多 1 次；循环路径被拒绝 |
| 6 个边界案例 | 历史边界总通过率 6/12 | 选定 6 例均在模型前确定性返回，模型调用 0 |
| 6 个历史超时题模拟 | 历史均约 180 秒无完成结果 | Mock 超时后 6/6 保留受控部分答案 |
| 6 个错误审查案例 | 历史错误检测总计 1/12 | 选定 6/6 定位指定第一错误步骤 |

节点耗时由 `solver_observability.node_timings` 按请求记录。本轮没有真实
Provider 调用，因此不把本地毫秒级规则耗时外推为生产 P50/P95。定向测试未
出现硬超时。

## 4. 未执行测试

- 未运行完整 336 例 live 测试：用户明确要求本轮不强制全量重跑，且它会产生
  长时间真实 Provider 调用和成本；
- 未重新计算严格准确率、条件准确率、评分覆盖率和课程回退率；
- 未验证真实 Spark/Qwen 可用性、真实多图 OCR 质量和生产网络延迟；
- 未做 DSP、COMM Prompt 定向调优，避免对极少有效样本过拟合；
- 未运行 Docker 端到端测试；本轮范围是服务层定向优化。

## 5. 最终结果

| 检查 | 结果 |
|---|---|
| 配置校验 `scripts/validate_config.py` | 通过 |
| 敏感文件扫描 `scripts/check_sensitive_files.py` | 通过 |
| 全仓 Ruff | 通过 |
| 全仓 Mypy | 通过，196 个源文件无问题 |
| 定向/兼容 Pytest | 66 passed，2 warnings |
| 全量仓库 Pytest | 545 passed，15 skipped，5 warnings |
| 全量测试覆盖率 | 83% |
| OpenAPI 导出 | 通过，`docs/api/openapi.json` 已更新 |
| Docker Compose 配置 | 通过 |
| `git diff --check` | 通过；只有 Windows 行尾转换提示 |

全量仓库 Pytest 耗时 287.16 秒。15 个 skip 是需要真实 API/模型环境的既有
集成测试；本轮没有把 skip 当作通过的 live 证据。预警来自 Starlette/httpx
弃用提示、未知 `requires_api_key` mark、本地 Qdrant payload index 和测试
SQLite 资源提示，未出现本轮新增异常。

`scripts/check.ps1` 首次整体调用被工具的 124 秒外层限制终止，并非检查失败；
随后逐项执行了脚本中的全部步骤，结果如上。

## 6. 剩余风险

- 规则校验器只覆盖明确可证明的有限规则，复杂拓扑仍需模型或人工复核；
- REVIEW 的六例通过不能代表完整 12 例和所有自由表达；
- 请求级 175 秒硬截止可避免进入任务 180 秒边界，但真实任务调度、RAG 和
  Provider 取消传播仍需 live 验证；
- 多图逐图模式的 N 次视觉调用虽有并发和预算，仍可能成为长尾来源；
- 模型 route fallback 的供应商可用性问题不能由本地路由代码消除；
- 当前分支包含用户先前未提交的教学闭环修改，提交前必须继续按意图审查范围。

## 7. 回滚

```bash
git log --oneline
git revert <commit>
```

当前工作区有未提交用户代码，不使用破坏性 reset。
