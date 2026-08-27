# 问题登记表

| ID | 严重度 | 类别 | 现象与证据 | 影响 | 根因状态 |
|---|---|---|---|---|---|
| CONTEXT-001 | P0 | context/UX | 同会话追问“直接给出公式，不要资料说明”后回答无关 KCL/KVL，未给出前一轮公式 | 核心多轮学习失信 | 未确认；疑似 continuity/route/plan 断裂 |
| UI-STATE-001 | P1 | frontend/state | 纯文本新任务仍显示上一任务 5V 分压电路图 artifact | 用户可能把旧产物当当前答案 | 未确认；疑似 presentation 清理/ownership |
| E2E-001 | P1 | API/runtime | `/api/v1/chat` 简单问题 202 后 `runtime_node_error`、无 result | API 消费者无法完成基础问答 | 未确认；疑似兼容链路与 tasks 链路分叉 |
| ROUTER-001 | P1 | router/planner | route Agent=knowledge QA，Planner capability=knowledge.govern，最终 validation insufficient | 简单问题被错误目标阻断 | 未确认；疑似 ID 粒度/绑定不一致 |
| RAG-001 | P1 | RAG | 随机不存在知识词仍返回 3 条且无 warning | 无关课程资料可能被当证据 | 未确认；疑似阈值/abstention 缺失 |
| RESEARCH-001 | P1 | research | 随机不存在研究词仍返回 5 条无关候选且无 warning | 研究者可能误读或误引用 | 未确认；疑似相关性过滤缺失 |
| TASK-CTRL-001 | P1 | task control | cancel 后 >40 s 仍 running，约 51 s 才 cancelled | 停止按钮不符合直觉，资源持续占用 | 未确认；疑似协作式取消/外部调用不可中断 |
| READINESS-001 | P1 | release | readiness 9 场景全部 production_ready=false | 可见能力与发布预期冲突 | 配置事实已确认，产品策略待定 |
| ARCH-001 | P1 | architecture | 实际 `/workspace` 是 legacy；React 源码/构建不在实际入口 | 修改/测试错误表面，持续产生 UI 漂移 | 路由事实已确认 |
| PERF-001 | P2 | observability | 失败 debug waterfall 多段 0 ms，无法解释实际 3.254 s 节点 | RCA 和性能治理困难 | 未确认；失败路径埋点缺失 |
| UX-001 | P2 | frontend/UX | Runtime 内部词、失败/部分产物/验证状态混排 | 学习者难以判断是否可信 | UI 文案/信息架构问题 |
| DISCOVERY-001 | P2 | discovery | 后端 9 场景、工作台 6 showcase，能力发现不一致 | 功能不可发现/预期不一致 | 路由与 catalog 事实已确认 |
| SESSION-001 | P2 | session UX | 侧栏存在大量重复“新会话 · 0 条消息”，历史定位成本高 | 会话管理不顺手 | 可能是历史数据/刷新时机，未确认 |
| FILE-001 | P2 | file API | content endpoint 不带 user_id 返回 422 | API 使用门槛高，错误可理解性差 | 契约设计事实已确认 |
| HEALTH-001 | P2 | health | models health `live=false` 但 providers available=true；实际 chat 失败 | 运维/用户误判可用性 | 健康字段语义待统一 |

严重度定义：P0 核心任务/信任链直接不可接受；P1 主要功能错误、数据/证据误导或发布阻塞；P2 明显体验、维护和可观测性问题；P3 本轮没有新增需要登记的低优先级问题。
