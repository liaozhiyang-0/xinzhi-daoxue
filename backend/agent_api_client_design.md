# 星辰 Agent API 调用设计

## 配置项

```text
XF_AGENT_API_KEY=your_api_key_here
XF_AGENT_BASE_URL=your_xf_agent_base_url_here
```

配置从环境变量读取，不允许写入真实密钥到代码或仓库。

## 调用流程

1. 前端调用自研后端业务接口。
2. 后端校验请求参数和用户上下文。
3. 后端根据业务类型选择对应 Agent。
4. 后端拼接课程资料、知识点、题目、历史记录等上下文。
5. 后端使用 `XF_AGENT_API_KEY` 调用星辰 Agent API。
6. 后端校验 Agent 返回结构，必要时做字段兜底。
7. 后端保存记录并返回前端。

## 客户端封装建议

- 统一封装 `AgentApiClient`。
- 支持请求超时、重试、错误码映射和日志记录。
- 不在日志中打印完整 API Key 或敏感请求内容。
- 对 Agent 输出做 JSON Schema 校验，避免前端字段缺失。

## 伪代码

```python
class AgentApiClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def invoke(self, agent_id: str, payload: dict) -> dict:
        headers = {
            "Authorization": "Bearer XF_AGENT_API_KEY",
            "Content-Type": "application/json",
        }
        request_body = {
            "agent_id": agent_id,
            "input": payload,
        }
        # 实现时替换为真实 HTTP 客户端调用。
        return {
            "status": "placeholder",
            "data": {},
        }
```

## Agent 映射

| 业务能力 | Agent | 后端接口 |
| --- | --- | --- |
| 智能问答 | 课程问答 Agent | `/api/v1/student/qa` |
| 错题诊断 | 错题诊断 Agent | `/api/v1/student/wrong-question/diagnose` |
| 学习建议 | 学习规划 Agent | `/api/v1/student/study-suggestion` |
| 教师分析 | 教师分析 Agent | `/api/v1/teacher/teaching-suggestion` |
