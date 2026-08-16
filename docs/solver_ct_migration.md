# SolverCT 兼容迁移

SOLVER_CT_V1 不再是本地求解架构中心。它仅作为冻结的 CT 历史基线和旧版本效果对照，不参与当前 Runtime 回退。

| 旧字段 | 通用字段 |
|---|---|
| components | entities |
| circuit_relations | relations + equations_given |
| reference_directions | reference_conventions |

`LocalCircuitSolverGraph.run()` 保留同步签名和 fast/full/blocked 兼容输出，但内部构造 AcademicProblem 并调用 AcademicProblemSolverGraph。旧文件不再包含第二套 StateGraph 或通用求解核心。

历史外部工作流代码与配置已移除；本地迁移测试只证明当前 Local Runtime 的合同和执行边界，不代表真实模型答案质量。
