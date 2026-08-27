# 会议演示 V2 指南

## 会前

```powershell
.\xzd.ps1 start
.\.venv\Scripts\python.exe scripts\demo_cli.py preflight --base-url http://127.0.0.1:8000
```

先检查 API、索引、LEARN Flow 和 `ACADEMIC_PROBLEM_SOLVER` 本地能力。真实云端演示会消耗额度，截图回归与真实云端回归分开执行。

## 四条故事线

1. 多课程知识问答：分别选择 CT、AE、DE，强调统一入口和课程路由。
2. 本地 RAG 与云端工作流协作：提问后打开资料依据、执行过程，再点击正文 S 编号。
3. 电路理论专业解题：先文字题，再图片题；明确“题目解答”和“方法参考”不是同一证据语义。
4. 多智能体扩展与稳定降级：展示未发布 Agent、开发态 Mock 和本地 fallback 标签。

## 真实 Trace

演示中心的“读取最近真实执行”使用浏览器最近完成的 task_id 调用统一 Execution Debug 接口，再绘制步骤；没有预设假过程。需要深入时打开 `/debug/execution?task_id=...`。

## 1280×720

使用 `/workspace?presentation=1`。左侧栏自动收窄，右侧上下文默认打开，隐藏不必要设置并提供一键退出。输入框固定可见，页面无横向滚动。
