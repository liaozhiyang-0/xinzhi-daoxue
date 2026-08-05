# P18 教师 OCR 队列聚焦筛选

## 目标

P17 已让教师看到 OCR 快照新鲜度和决策证据；P18 进一步降低长队列的复核成本。页面在已有只读快照上增加按复核动作、优先级和决策状态的本地筛选，不新增数据库字段，也不改变 OCR 或 Provider 调用链。

## 行为边界

- 筛选只作用于当前已经加载的响应，不会重新扫描资料或触发 OCR。
- `Review action` 来自接口的 `summary.by_action`，避免前端维护候选文件清单。
- `Priority` 支持 `high`、`medium`；`Decision` 支持 `pending`、`decided`。
- 页面同时显示“显示行数 / 总候选数”；筛选无结果时明确提示，而不是误报为空队列。
- 切换课程或刷新后，仍保留有效筛选；如果新课程不存在该动作，则自动回到全部动作。

## 验证

```powershell
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\pytest.exe apps/api/tests/test_teacher_web.py -q --no-cov
```

浏览器验收应确认：默认显示全部候选；选择 `High` 后只显示高优先级行；选择 `Pending` 后只显示待决策行；页面计数随筛选变化，控制台无 error/warn。

本阶段没有执行真实 OCR、Provider 或 Docker，也没有处理用户自行设计的三个演示案例。
