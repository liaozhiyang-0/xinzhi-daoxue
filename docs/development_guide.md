# Development Guide

Windows：

```powershell
.\xzd.cmd doctor
.\xzd.cmd start -Reload
```

手动模式：

```powershell
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload
```

Linux/macOS：

```sh
./xzd.sh doctor
./xzd.sh start --reload
```

新增 Agent 应先声明注册表能力、输入模式、执行模式、Provider、超时和回退，再实现处理器。业务 Agent 只通过本地 Runtime、统一 ModelService 或确定性工具执行，不在业务代码内拼接供应商 HTTP。数据库变化必须新增 migration；事件变化必须补 SSE 顺序和重连测试。

原始教材只读，真实 `.env`、教材、向量、上传和缓存均不得提交。
