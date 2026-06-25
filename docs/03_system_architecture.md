# 系统架构

## 分层架构

### 用户层

包括学生、教师和院系管理者。学生关注题图解题、课程问答、学习反馈和学习建议；教师关注班级学情、薄弱知识点和教学建议；院系管理者关注课程群建设效果。

### 前端应用层

采用 Vue3 + TypeScript + Element Plus + ECharts。学生端提供课程选择、题图解题、智能问答、简单纠错、学习建议和历史记录；教师端提供统计看板、趋势图和教学建议。

### 自研业务服务层

负责用户、课程、知识点、题库、问答记录、题图解题记录、错因提示记录、学习画像、统计分析和 Agent 调用编排。第一版可选择 Spring Boot 或 FastAPI 实现。

### 讯飞星辰 Agent 层

封装识图解题 Agent、课程问答 Agent、学习规划 Agent 和教师分析 Agent。课程问答 Agent 内部保留简单纠错和错因提示能力。Agent 使用课程资料库、题库、错因标签、题图解题样例和业务上下文生成结构化输出。

### 讯飞星火 MaaS 层

用于图文解题样例构造、批量推理、模型评估和后续可选微调。第一版先沉淀识图解题评估样例、Prompt、评估指标和数据生产流程。

### 数据与知识层

包括 MySQL / PostgreSQL、Redis、MinIO、课程知识库、题库、错题库、学习记录和统计结果。

### 运维部署层

采用 Docker Compose 组织 frontend、backend、mysql、redis、minio 和 nginx，后续可扩展到 Kubernetes。

## 文本结构图

```text
[学生 / 教师 / 院系管理者]
          |
          v
[前端应用层 Vue3 + Element Plus + ECharts]
          |
          v
[自研业务服务层 Spring Boot / FastAPI]
   |          |            |              |
   v          v            v              v
[识图解题] [课程问答+简单纠错] [学习规划] [教师分析]  <- 星辰 Agent 层
          |
          v
[星火 MaaS 图文解题评估与后续微调平台]
          |
          v
[课程知识库 / 题库 / 错因标签 / 题图样例 / 学习画像 / 统计数据]
          |
          v
[MySQL or PostgreSQL / Redis / MinIO / Nginx / Docker Compose]
```
