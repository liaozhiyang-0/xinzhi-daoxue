# 测试用例矩阵

| ID | 面 | 输入/动作 | 入口 | 结果 | 结论 |
|---|---|---|---|---|---|
| B-01 | 浏览器启动 | 打开 `/workspace` | 浏览器 | 200、三栏工作台、游客模式 | 通过 |
| B-02 | 新会话 | 点击“新建会话” | 浏览器 | 六张 showcase 卡片出现，可输入 | 通过，但 UI 只覆盖 6 个场景 |
| B-03 | 单轮问答 | 解释串联电阻电流/总电阻 | `/workspace` -> tasks | 约 12 s 完成，内容基本正确，但旧电路图残留、证据含无关 S1 | P1 |
| B-04 | 多轮追问 | “直接给出公式，不要资料说明” | 同一会话 | 输出无关 KCL/KVL 说明，未遵守格式 | P0 |
| B-05 | 刷新恢复 | reload 同一会话 | 浏览器 | 两轮消息和错误回答恢复 | 通过恢复机制；内容错误仍保留 |
| API-01 | 兼容 chat | 简单串联电阻问题 | `POST /api/v1/chat` | 202 后 `runtime_node_error`，无 result | P1 |
| API-02 | tasks 路由 | explain_concept 简单问题 | `POST /api/v1/tasks` | 路由与 Planner 目标不一致，验证失败 | P1 |
| API-03 | SSE | `Last-Event-ID: 0/10/16` | task stream | 事件按 1..17 连续重放 | 通过 |
| API-04 | 取消 | research task 立即 cancel | tasks | >40 s 仍运行，约 51 s 后 cancelled | P1 |
| API-05 | readiness | 查询 9 场景 | scenarios | 全部 production_ready=false | 发布阻塞 |
| FILE-01 | 文件入库 | 上传 README.txt | `POST /api/v1/files` | 201、ready、抽取文本、1 chunk | 通过 |
| FILE-02 | 文件内容接口 | 不带 user_id 请求 content | files | 422 参数错误 | API 易用性风险 |
| RAG-01 | 已知检索 | `串联电阻总电阻` | knowledge search | 相关 CT 片段 | 通过 |
| RAG-02 | 无匹配检索 | 随机不存在术语 | knowledge/rag-search | 仍返回 3 条，无 warning | P1 |
| RES-01 | 已知研究检索 | 医学影像基础模型 | research search | 返回候选论文 | 需逐条核验 |
| RES-02 | 无匹配研究检索 | `zzzz-no-such...` | research search | 仍返回 5 条，无 warning | P1 |
| OPS-01 | 健康 | `/health`、RAG、models | API | 基础依赖健康；models live=false | 需区分健康语义 |
| QA-01 | 静态质量 | Ruff/Mypy/TS/config/sensitive/drift | CLI | 均通过 | 代码质量不等于运行链路通过 |

完整问题登记见 `15_issue_register.md` 和 `issue_register.csv`。
