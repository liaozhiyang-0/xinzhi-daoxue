# 讯飞模型与星辰集成

七个工作流继续通过同一星辰 Provider 调用。已验证协议保持：同步 `stream=false`、`Bearer key:secret`、文字参数 `AGENT_USER_INPUT`、单图片参数 `USER_INPUT_image`。不得把多图数组、PDF 或未知参数直接传入该接口。

`XingchenWorkflowProvider` 提供通用 `invoke_workflow` 边界，只允许调用注册表中已配置的 Flow ID，并将超时、连接、HTTP 与解析错误标准化。实际任务链继续复用已验证的 `XingchenCloudProvider`。

`IflytekSparkProvider` 使用讯飞官方 OpenAI 兼容 HTTP Chat Completions，新配置为 `IFLYTEK_SPARK_BASE_URL`、`IFLYTEK_SPARK_API_KEY`、`IFLYTEK_SPARK_MODEL`。旧 `SPARK_API_PASSWORD` 仅保留兼容读取，且仍受 `SPARK_ENABLED` 控制。模型 HTTP 鉴权不是星辰 Workflow 的 Key/Secret，也不会从 `SPARK_API_KEY`/`SPARK_API_SECRET` 猜测 APIPassword。

配置完整不代表工作流当前发布、授权或回答质量已验证。Mock、本地回退、历史云端回归与当前真实云端验证必须分别报告。
