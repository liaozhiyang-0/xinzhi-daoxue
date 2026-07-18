# 学生端 Web v1 指南

启动API后访问：`http://127.0.0.1:8000/student`。

首版提供CT/AE/DE知识问答、CT文字完整解题、CT单图片解题、轻量连续追问、知识库来源、相关教材图片和本地降级提示。计划中的批改、教学与科研Agent不会以Mock结果出现在正式学生操作区。

学生业务请求只提交到统一`POST /api/v1/tasks`；会话使用现有`/sessions`，附件使用现有`/files`，进度复用现有任务SSE。前端不直接访问星辰或Debug接口。AE/DE完整求解会在页面提前显示“该课程完整解题工作流尚未开放”，后端路由仍保留相同边界。

图片仅允许一张jpg/jpeg/png/webp，默认最大8MB。服务端校验扩展名、MIME和图片签名，限制像素，修正EXIF方向并重新编码，不向浏览器返回绝对路径；未关联任务的学生图片带过期时间，后续上传时清理过期记录和对象。不支持PDF或多图片。

会话只保存当前/上一课程、上一意图与Agent、截断回答摘要、截断对话摘要和最多10个证据ID。摘要由本地规则截取，不调用额外模型；课程切换会清空上一课程答案、对话和证据上下文。新建会话即可清空，不提供跨会话画像或长期记忆。

正式LEARN/SOLVER发生本地开发Mock、fallback或风险时会以醒目提示展示；计划中的未来Agent只显示“开发中”，不向学生返回其开发态Mock。学生页不显示内部Prompt、Qdrant point、向量、完整Trace、Flow或凭据。

验证命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q apps/api/tests/test_student_web.py
```

真实浏览器渲染可使用Edge headless访问`/student`；完整业务仍通过现有任务API和SSE验证，不需要Debug接口。

安装Playwright开发依赖后，可运行`scripts/student_browser_smoke.js`。测试服务必须使用`APP_ENV=test`、`XINGCHEN_ENABLED=false`、`RAG_ENABLED=false`和本地Mock；通过`XINZHI_BROWSER_BASE_URL`、`XINZHI_BROWSER_TEST_IMAGE`、`XINZHI_BROWSER_INVALID_FILE`提供地址与测试文件。脚本不会调用真实星辰。
