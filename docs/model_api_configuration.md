# 国产多模型 API 配置

本地 Supervisor 通过 `config/models.yaml` 和 `config/model_routes.yaml` 选择模型，业务 Agent 只调用统一 `ModelService`。Spark 模型 API、Qwen 模型 API 与原有星辰 Workflow Provider 使用独立配置，不共享密钥或请求协议。

## 最小配置

复制模板：

```powershell
Copy-Item .env.example .env
```

或：

```bash
cp .env.example .env
```

基础模型测试只需填写：

```env
IFLYTEK_SPARK_API_KEY=
DASHSCOPE_API_KEY=
```

- `IFLYTEK_SPARK_API_KEY`：讯飞 Spark-X2 HTTP APIPassword，或控制台当前要求的 `APIKey:APISecret` 形式。
- `DASHSCOPE_API_KEY`：阿里云百炼 API Key。
- `DASHSCOPE_WORKSPACE_ID`：仅业务空间专属域名需要；默认公共兼容地址不需要。
- `DASHSCOPE_BASE_URL`：显式配置时优先；留空且有 Workspace ID 时按地域拼接；两者都没有时使用北京公共兼容地址。

Key 为空不会阻止服务启动。对应 Provider 显示为 `unconfigured`，调用时返回明确配置错误，本地 RAG 与星辰工作流不受影响。

## 模型与职责

| 别名 | Provider / model | 用途 |
|---|---|---|
| `spark_reasoner` | `iflytek_spark / spark-x` | 复杂推理、课程问答、电路规划、审校 |
| `qwen_vision_primary` | `dashscope / qwen3.7-plus` | 电路图、多图、公式、表格、扫描件 |
| `qwen_vision_fast` | `dashscope / qwen3.6-flash` | 普通图片与快速视觉回退 |
| `qwen_text_fast` | `dashscope / qwen3.5-flash` | 分类、改写、摘要、JSON |

注册表声明模型能力，任务路由声明主模型、回退和可选校验模型。Provider 内没有业务路由。

## 安装、启动与检查

```powershell
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
.\xzd.cmd start -Reload
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --config-only
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --provider iflytek
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --provider dashscope
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --all
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --vision .\path\to\test.png
```

`--config-only` 不发送请求。其他命令是显式真实 API 测试，会消耗少量额度。退出码为：0 全部通过、1 存在调用失败、2 配置不完整。

HTTP 接口：

```text
GET /api/v1/models
GET /api/v1/models/health?live=false
GET /api/v1/models/health?live=true
GET /api/v1/internal-agents
```

`live=false` 只检查配置和注册表；`live=true` 对每个已配置 Provider 发送一句极短文本，不启用深度思考、不发送图片。

## 内部 Agent 批量评测

先执行不发请求的配置检查：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_model_agents.py --dry-run
```

真实批量评测必须显式执行，并建议先按 Agent 或 case 分批：

```powershell
# 低成本分类与改写
.\.venv\Scripts\python.exe scripts\evaluate_model_agents.py `
  --agent COURSE_CLASSIFIER_LOCAL_V1 `
  --agent INTENT_CLASSIFIER_LOCAL_V1 `
  --agent QUERY_REWRITER_LOCAL_V1 `
  --max-total-tokens 2500 --max-output-tokens 256

# 单个复杂 Agent，便于控制额度和定位失败
.\.venv\Scripts\python.exe scripts\evaluate_model_agents.py `
  --case circuit_plan_missing_direction `
  --max-total-tokens 1800 --max-output-tokens 384
```

案例位于 `evaluation/model_agents/cases.yaml`。脱敏报告写入 Git 忽略的 `local_storage/evaluations/model_agents_*.json`，只包含状态、模型、耗时、Token、请求 ID 和输出字段名，不保存完整提示词、答案或图片。`--max-total-tokens` 会在案例之间停止后续调用；单个请求的输入 Token 由 Provider 计量，因此最后一个案例可能使总量略微超过阈值。

Spark 驱动的结构化内部 Agent 使用两段链：Spark 生成业务草稿，Qwen3.5 将草稿归一为 Pydantic JSON。报告中的 Token、耗时和模型名称（例如 `spark-x->qwen3.5-flash`）覆盖两个阶段，不能只按第二阶段估算费用。

## 图片处理边界

Qwen Provider 接受公网 HTTP(S) URL、本地路径与 Base64 Data URL。项目会校验 JPEG、PNG、WEBP、BMP、TIFF，默认单张不超过 6MB、一次不超过 8 张、长边不超过 4096 像素；本地图片自动纠正 EXIF 方向并默认移除 EXIF。图片正文和 Base64 不进入日志。

复杂电路图、密集公式、小字号参数或扫描件可通过路由启用 `vl_high_resolution_images`。普通截图默认关闭，以控制 Token 和耗时。

## 重试、回退与安全

- 连接错误、读取超时、429、502、503 最多自动重试一次；主模型仍失败后才尝试路由回退。
- 鉴权、模型名、输入格式、文件格式、上下文超限和结构校验错误不自动重试。
- 结构校验错误也不触发模型回退；应先修正 Schema、提示词或评测输入，避免为相同业务缺失重复计费。
- 全局、Spark、Qwen、视觉并发默认分别为 6、2、4、2，可通过 `.env` 调整。
- Trace 只保存 Provider、模型、任务类型、耗时、Token、图片数量、请求 ID、重试与回退状态、输入摘要哈希；不保存 Key、Authorization、Base64、完整提示词或完整思考过程。
- 正式 `ModelResponse` 序列化会排除 `reasoning_content`；流式推理只发出“存在推理增量”的元数据，不发送内容。

## 常见错误

| 提示 | 处理方式 |
|---|---|
| `IFLYTEK_SPARK_API_KEY未配置` | 在 `.env` 填写 Spark-X2 HTTP 凭据并重启 |
| 讯飞 401 | 检查 HTTP APIPassword 或控制台要求的 AK:SK 格式 |
| `DASHSCOPE_API_KEY未配置` | 在 `.env` 填写百炼 Key 并重启 |
| 百炼 401 | 检查 API Key 与地域 |
| 百炼 404 | 检查模型名、Base URL 与业务空间 |
| 图片超限 | 压缩图片或调整项目限制；错误会显示当前大小与限制 |
| 模型超时 | 查看模型 Trace 中的重试和 `fallback_used` 状态 |

## 星辰工作流继续保留

原有 `XINGCHEN_*_FLOW_ID`、`XINGCHEN_API_KEY`、`XINGCHEN_API_SECRET` 均不属于本次模型 API。`SOLVER_CT_V1` 的已验证文字/单图片链路没有修改；未配置模型 Key 时仍保留原有星辰、Mock 和本地检索边界。

本地 BGE、SigLIP2、可选 reranker、Qdrant、PostgreSQL、Redis 和 MinIO 也不是付费模型 API，不需要上述 Key。
