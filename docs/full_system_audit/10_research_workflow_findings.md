# 研究工作流发现

## 可用部分

研究场景可被 catalog 路由到 `RESEARCH_01_ACADEMIC_SEARCH_V1`，研究知识集合存在并有 305 条 active 记录；已知医学影像 query 能返回 OpenAlex/arXiv 候选。场景契约要求标题摘要、日期、DOI/arXiv、检索时间和链接，方向是正确的。

## 主要风险

随机不存在的研究 query 仍返回 5 条候选，主题包括硬件木马、器官水凝胶、旅行行为、牙科地标和柔性 TFT，和 query 无关；接口没有 `no_match` 或 `relevance_warning`。这会把“候选搜索结果”误读为“关于该主题的论文”。

研究 readiness 明确要求人工复核，且 `production_ready=false`，但前端研究卡片仍是可触达的 showcase。产品必须在列表级别标记“候选/待核验”，不能只在场景说明中写 review boundary。

## 取消与长任务

研究任务取消被接受后，约 40 秒仍显示 running，约 51 秒才 cancelled。研究搜索涉及外部来源时，停止按钮需要给出“正在请求停止，外部请求可能尚未返回”的状态和可见的终止 deadline，避免用户重复点击或关闭页面后无法判断。

## 未验证

本轮没有对 DOI 去重、日期边界、原文打开、引用字段完整性和论文摘要事实一致性做逐条人工核验，因此不输出研究结果准确率。
