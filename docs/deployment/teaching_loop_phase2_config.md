# 教学闭环第二阶段配置与运行

第二阶段默认随现有 Workspace 启用，无需新服务、数据库迁移或云端凭据。启动：

```powershell
.\xzd.cmd start
```

打开 `http://127.0.0.1:8000/workspace`，在输入框上方选择“直接解答”“分步辅导”
或“检查我的步骤”。检查模式只接受文字过程；图片草稿不做首错识别。

唯一新增开关：

```env
STUDENT_VERIFICATION_MODEL_ENABLED=false
```

该值必须保持默认关闭；当前版本没有启用模型裁判路径。外部模型 Provider 不因
选择教学模式而自动开启。

专项验证：

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_teaching_loop_phase2_services.py apps/api/tests/test_teaching_loop_phase2_integration.py apps/api/tests/test_teaching_loop_phase2_evaluation.py
.\.venv\Scripts\python.exe scripts\run_evaluation.py --offline --tag teaching_loop_phase2 --no-cache
```

离线评测使用现有 sessions/tasks API 与本地确定性/Mock 边界，不证明真实模型的
教学质量。
