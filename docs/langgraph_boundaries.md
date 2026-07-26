# LangGraph 使用边界

LangGraph 用于 Supervisor、复杂 Knowledge QA、Academic Problem Solver、复杂 Data Analysis 和需要中断恢复的批改流程。它管理状态、条件边、重试、恢复和流式阶段。

普通 Python 服务负责文件/PDF/图片预处理、Embedding、RAG、数学、单位、代码沙箱、数据库、图表和格式转换。节点只调用注入服务，不自行连接外部资源。

禁止在状态中放完整 Base64、PDF、DataFrame、密钥、教材全文、隐藏推理或超大原始响应。XZDGraphState 只保存引用、摘要、结构化结果和 bounded trace。

简单教案、固定格式、单步摘要、旧星辰封装、健康检查和文件预处理不强制包装为图节点。
