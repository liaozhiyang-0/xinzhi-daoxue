# Migration Roadmap

## 已完成

- A：仓库审计、统一 V2 协议、Provider 边界、注册元数据、旧任务接口适配。
- B：Supervisor 规则路由、本地安全回退、节点 Trace、新版 chat/capabilities/workflows API。
- C：新版 `/chat` 以本地 RAG 为知识问答主路径；增加星火 grounded generation、旧哈希兼容 Provider、迁移/重建脚本，并复用真实 BGE + Qdrant 混合检索。
- D 骨架：多图逐张限并发、结果合并、PDF 文本层提取和限制；单图旧链路未改。
- E 骨架：电路题结构契约、快速/完整路径选择、calculator/SymPy/unit checker。

## 未完成

1. 多图与 PDF 的提取结果尚未写入主任务上下文；当前 `/chat` 会安全本地回退。
2. 专用讯飞 Vision 传输字段尚未完成真实协议验证，Provider 不会猜测调用。
3. 电路题能力已统一归入当前 `ACADEMIC_PROBLEM_SOLVER`；旧 `SOLVER_CT_V1` 及其专用开关属于退役历史资产，不再作为活动执行路径。
4. 本地知识问答的真实星火质量、延迟和引用遵循性尚未使用当前凭据验收。
5. SS/DSP/COMM/RF/EM/INFO/EMBEDDED/IC 只有统一编码，尚无本地课程语料或专用 Agent。
