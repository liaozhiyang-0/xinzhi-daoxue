# 会议演示指南

## 会前准备

1. 保持 `.env` 和模型密钥不变，不在会议现场编辑。
2. 启动 Qdrant 和所需本地依赖，确认 CT/AE/DE 索引版本正确。
3. 运行 `powershell -ExecutionPolicy Bypass -File .\scripts\start_demo.ps1`。
4. 如果服务已在运行，单独执行 `.\.venv\Scripts\python.exe scripts\demo_cli.py preflight`。
5. 默认 Preflight 不消耗外部模型额度；只有明确需要真实模型探测时才加 `--with-cloud`。

页面地址：`http://127.0.0.1:8000/`、`/student`、`/demo?presentation=1`。需要模型 Provider 时可能等待，演示时应提前说明耗时来自模型和检索加载。

## 推荐顺序

1. 统一首页：说明三课程、专业解题、本地多模态 RAG 和扩展框架。
2. 三课程知识问答：依次使用 CT、AE、DE 固定概念题。
3. 电路理论文字题，再展示图片上传与预览。
4. 展开“参考课程资料”，说明回答可追溯。
5. 进入 RAG 调试，展示 BM25、Dense、融合、Evidence 与 Citation。
6. 演示复杂整题的 misrouted 工作流边界。
7. 在演示中心载入“稳定降级”，展示本地 Runtime 的边界回答。
8. 进入 Agent 管理，说明 Published、Mock ready、Planned 与配置驱动接入。

## 故障处理

- 页面打不开：先访问 `/api/v1/health`，再检查 FastAPI 端口。
- RAG 降级：检查 Qdrant 和索引版本，不要现场重建全部索引。
- 模型超时：切换演示中心“稳定降级”场景，不修改 `.env`。
- 图片失败：使用清晰 PNG/JPEG/WebP 且小于 8MB；也可只展示上传预览。
- 状态接口失败：系统页仍会打开并标记无法获取。

演示结束后，使用启动脚本打印的 PID 执行 `Stop-Process -Id <PID>`；不要结束非本次启动的共享 Qdrant。不要在现场打印 `.env`、完整 Trace 或 Authorization。
