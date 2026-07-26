# CoursePack 设计

CoursePack 是课程规则包，不是 Agent，也不持有或调用 ModelService/Provider。接口位于 `apps/api/app/courses/base.py`，包含问题归一化、题型分类、能力选择、提示模板、结构/结果校验、答案格式和回退配置。运行时唯一注册表是 CourseRegistry。

| 课程 | 状态 | 题型范围 | 回退 |
|---|---|---|---|
| CT | implemented | KCL/KVL、节点、网孔、定理、一二阶、相量、功率、受控源、互感、二端口、频响 | 高风险可指向 SOLVER_CT_V1 |
| AE | basic | 二极管、BJT/MOS 工作点、小信号、反馈、频响、运放、波形电路 | 本地条件化结果 |
| DE | basic | 编码、逻辑化简、组合/时序、触发器、计数器、状态机、Verilog | 本地条件化结果 |
| SS | basic | 连续/离散信号、系统性质、卷积、Fourier/Laplace/Z、频域 | 本地条件化结果 |
| DSP/COMM/RF/EM/INFO/EMBEDDED/IC | skeleton | 仅注册与扩展边界 | CONDITIONAL |

新增课程只注册一个 CoursePack，声明题型、关键词、能力和回退，不复制求解图。
