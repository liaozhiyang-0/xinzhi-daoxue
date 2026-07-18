# Agent 脚手架指南

预览：

```powershell
python scripts/agent_cli.py scaffold DEMO_01_SAMPLE_V1 --display-name "样例工作流" --dry-run
```

生成：

```powershell
python scripts/agent_cli.py scaffold DEMO_01_SAMPLE_V1 `
  --display-name "样例工作流" `
  --courses CT,AE,DE `
  --intents general_qa `
  --required-inputs question,course_id `
  --optional-inputs request_id,conversation_summary `
  --output-fields summary,items `
  --retrieval-policy text_rag `
  --mock-profile demo_sample_v1
```

默认写入`agent_configs/scaffolds/<AGENT_ID>/`，生成AgentDefinition片段、Flow环境变量占位、Mock profile、三类fixture、契约测试模板、显式真实云端测试模板、Debug请求和接入清单。默认`enabled=false`、`publication_status=planned`，不含Flow值或凭据，不创建Provider或TaskRunner分支。

已有文件不会覆盖；`--force`会在结果中明确警告。生成后把配置/profile/fixture分别合并到唯一注册文件、统一profile文件和fixture目录，再运行：

```powershell
python scripts/agent_cli.py validate
python scripts/agent_cli.py test-contract DEMO_01_SAMPLE_V1
python scripts/agent_cli.py compare-mock-cloud DEMO_01_SAMPLE_V1 --cloud-sample redacted.json
```

真实Flow填写到本机`.env`，先比较脱敏结构；只有显式真实测试通过后才设置`enabled=true`和`published`。
