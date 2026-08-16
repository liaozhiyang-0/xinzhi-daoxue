# 本地演示页面

访问 `http://localhost:8000/debug` 可使用原生 HTML/CSS/JavaScript 演示文字题和单图片题。两种输入共用会话、文件上传、非阻塞任务、SSE 和产物查询链路。

这是最小演示页面，不是正式学生端。页面不会读取或显示 API Key、Secret 和内部请求体；业务任务统一由后端 Local Runtime 完成。

页面显示当前步骤、耗时、Provider、题目摘要、完整解答、关键公式、最终答案、风险和知识库来源。Mock 结果使用黄色标识，真实模型结果按 Provider 状态标识。

文字 `SOLVER_CT` 可使用最多 3 条、合计不超过 2000 字的本地方法参考；图片题不按文件名或空文本检索，直接进入本地多模态 Runtime。

图片首先保存到本地 MinIO 或回退目录并关联任务，随后由本地 Runtime 进行视觉处理；当前只支持单张 PNG/JPG/JPEG。
