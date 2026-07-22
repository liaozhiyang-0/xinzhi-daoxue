# SolverCT 兼容迁移

SOLVER_CT_V1 不再是本地求解架构中心。它仍作为冻结的 CT 云端基线、CoursePack 高风险回退目标和旧版本效果对照。

| 旧字段 | 通用字段 |
|---|---|
| components | entities |
| circuit_relations | relations + equations_given |
| reference_directions | reference_conventions |

`LocalCircuitSolverGraph.run()` 保留同步签名和 fast/full/blocked 兼容输出，但内部构造 AcademicProblem 并调用 AcademicProblemSolverGraph。旧文件不再包含第二套 StateGraph 或通用求解核心。

现有星辰 Flow、环境变量、Provider 与 HTTP 调用链未修改。真实云端答案质量仍须单独验收；本地迁移测试不能证明 Flow 的实时质量。
