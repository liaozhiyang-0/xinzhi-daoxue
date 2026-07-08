# 芯智导学：电子信息课程群垂类大模型系统

本仓库是面向科大讯飞星辰 Agent 平台的轻量 MVP。当前不开发独立前后端、不训练模型，只验证“课程知识库 + 多智能体 Prompt + 测试案例 + 演示流程”。

## MVP 范围

- 主课程：电路理论。
- 样例课程：模拟电子技术、数字电子技术（仅保留扩展框架）。
- 智能体：总控、课程问答、图片解析、学习规划、教师分析。
- 交付形式：Markdown 知识库、可复制 Prompt、测试案例和演示脚本。

## 目录

```text
docs/             MVP 范围、工作流、知识库、演示和评测计划
agent_configs/    可复制到星辰 Agent 的 Prompt
knowledge_base/   首版课程知识库
test_cases/       人工验收案例
demo/             演示脚本、输入和参考输出
archive_legacy/   重构前资料，只读保留，不作为首版上传内容
```

## 最短使用路径

1. 阅读 `docs/00_project_mvp.md`，确认首版边界。
2. 在星辰 Agent 创建智能体，复制 `agent_configs/` 中对应 Prompt。
3. 首批只上传 `knowledge_base/circuit_theory/`；按需补充模电、数电样例。
4. 按 `test_cases/` 逐项人工测试并记录结果。
5. 按 `demo/demo_script.md` 完成一次端到端演示。

本版本没有可执行程序或第三方依赖。验收以目录检查、Markdown 链接检查和星辰平台人工测试为准。
