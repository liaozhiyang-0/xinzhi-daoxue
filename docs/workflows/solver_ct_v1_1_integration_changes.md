# SOLVER_CT v1.1 integration 最小修改说明

## 版本与操作边界

- 保留并停止编辑云端 `SOLVER_CT_电路理论专业解题_v1.0`。
- 在讯飞星辰控制台复制 v1.0，新副本命名为 `SOLVER_CT_电路理论专业解题_v1.1_integration`。
- 本地基线 Tag 为 `baseline-xingchen-text-image-e2e`。
- 仓库没有收到星辰工作流原始 YAML，当前也没有可操作的已登录工作流编辑器，因此本轮**没有修改云端工作流**。下表是需要在副本中人工实施并重新发布/更新 API 绑定的具体说明。
- 已知的真实输入字段为 `AGENT_USER_INPUT`、`USER_INPUT_image`，已知最终组装节点名为 `final_response_text`。其余节点显示名必须在副本中按“定位方式”确认，不猜测 v1.0 的内部名称或 ID。

## 节点修改清单

| 顺序 | 副本中要定位的节点 | 最小修改字段 | 修改内容 | 原因 |
| --- | --- | --- | --- | --- |
| 1 | 开始节点（包含 `AGENT_USER_INPUT`、`USER_INPUT_image`） | 输入定义与连线 | 保持文字字段不变；确认 `USER_INPUT_image` 类型为 Image，且只连向现有图像识别节点 | 防止图片 URL 已上传但未进入识别链 |
| 2 | 直接消费 `USER_INPUT_image` 的图像识别/OCR 节点 | 输出变量 | 输出一个完整文本变量，例如 `image_problem_text`；要求保留元件值、单位、连接关系、端口标记和参考方向，不在此节点求解 | 题目结构化节点必须拿到完整识别结果 |
| 3 | 当前负责题目信息抽取/结构化的节点 | 输入映射、提示词 | 输入同时接收 `AGENT_USER_INPUT` 与 `image_problem_text`；优先使用非空图片识别文本，文字补充只作为用户要求；缺信息时生成明确假设和条件化求解条件，不循环要求用户补充 | 兼容文字/图片并减少反复追问 |
| 4 | 当前正确的电路求解主链 | 无 | 不改节点、不改连线、不增加重复推导节点 | 保留 v1.0 已验证的求解能力与回滚路径 |
| 5 | v1.0 中耗时最高的现有大模型节点（先在平台运行日志确认） | 提示词 | 删除重复题面、重复格式说明和已经由上游完成的推导；只保留该节点必要输入与一次推导要求。未确认耗时排名前不改其他节点 | 优先降低最慢节点耗时，避免无依据地改链路 |
| 6 | 最终回答组装节点 `final_response_text` | 输出格式、输出变量 | 固定输出下方 JSON；`answer_text` 必须保留面向学生的完整步骤。无证据时 `confidence` 输出 `null` | 让本地 Provider 可直接映射且不猜置信度 |
| 7 | 工作流结束节点 | `output` | `output` 只引用 `final_response_text` 的 JSON 字符串，不再拼接额外前后缀 | 避免合法 JSON 被包装文字破坏 |

## 题目信息不足时的最小提示词约束

添加到题目信息抽取/结构化节点，不要求新增节点：

```text
若题目信息足以在明确假设下求解，请列出假设并继续条件化作答。
只有缺少的信息会导致多个无法区分的关键拓扑或目标量时，才在 remaining_risks 中说明。
不要重复要求用户补充已经出现在文字或图片识别结果中的信息。
```

## 最终固定输出

`final_response_text` 只输出 JSON，不使用 Markdown 代码围栏：

```json
{
  "status": "completed",
  "input_type": "text_or_image",
  "answer_text": "面向学生的完整分步骤解答",
  "problem_summary": "题目条件、拓扑、目标量的简要摘要",
  "key_equations": ["关键公式"],
  "final_answer": "最终答案与单位",
  "assumptions": ["条件化作答所采用的假设"],
  "remaining_risks": ["仍需人工核对的信息"],
  "confidence": null
}
```

`input_type` 在运行时填 `text` 或 `image`。只有工作流已有可靠、可解释的置信度来源时才填写 `0～1` 数字，否则保持 `null`。

## 发布与回滚核对

1. 只编辑并发布 `SOLVER_CT_电路理论专业解题_v1.1_integration`。
2. 在 API 绑定页面执行“更新绑定”，确认 `AGENT_USER_INPUT` 与 `USER_INPUT_image` 均存在。
3. 用一条文字题和一张图片题在星辰平台调试，检查结束节点输出为单个 JSON 对象。
4. 将本地 `.env` 的 Flow ID 切换到 v1.1 副本并重新创建 API 容器，再做本地两次真实闭环。
5. 若出现识别或求解回归，将 Flow ID 恢复到 v1.0；本地代码可回滚到 Tag `baseline-xingchen-text-image-e2e`。

## LEARN_01 下一步接入点

当前唯一真实模型 Provider 只接受 `SOLVER_CT_V1`，所以 `LEARN_01_KNOWLEDGE_QA_V1` 本轮继续保持 `retrieval_only`，不会把一般课程问答错误送进电路求解工作流。下一步应在 `KnowledgeQAService` 已构造 `RetrievalContextPacket` 之后接入独立的通用学习问答 Provider，输入限制为 Top 3 短上下文，输出答案与原有 `kb://` 来源；路由和检索算法无需修改。
