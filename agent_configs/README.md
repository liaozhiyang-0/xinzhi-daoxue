# Agent 配置说明

本目录保存可复制到科大讯飞星辰 Agent 平台的 Prompt。建议先创建四个专业 Agent，再创建总控 Agent。

| 文件 | 用途 | 建议知识库 |
|---|---|---|
| `00_master_agent_prompt.md` | 意图判断和分流 | 可不挂载或仅挂载课程总览 |
| `01_course_qa_agent_prompt.md` | 概念问答、求解提示、纠错 | 电路理论全库 |
| `02_image_parsing_agent_prompt.md` | OCR 和电路结构化识别 | 读图说明、公式方法 |
| `03_learning_planner_agent_prompt.md` | 复习计划 | 总览、题型、错因标签 |
| `04_teacher_analysis_agent_prompt.md` | 匿名学情分析 | 总览、题型、错因标签 |

平台配置变化不写死在仓库中。每次修改 Prompt 后记录版本并重跑对应测试案例。
