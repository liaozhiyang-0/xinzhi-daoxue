# 系统架构

## 分层架构

### 用户层

包括学生、教师和院系管理者。学生关注问答、错题和学习建议；教师关注班级学情、薄弱知识点和教学建议；院系管理者关注课程群建设效果。

### 前端应用层

采用 Vue3 + TypeScript + Element Plus + ECharts。学生端提供课程选择、智能问答、错题诊断、学习建议和历史记录；教师端提供统计看板、趋势图和教学建议。

### 自研业务服务层

负责用户、课程、知识点、题库、问答记录、错题记录、学习画像、统计分析和 Agent 调用编排。第一版可选择 Spring Boot 或 FastAPI 实现。

### 讯飞星辰 Agent 层

封装课程问答 Agent、错题诊断 Agent、学习规划 Agent 和教师分析 Agent。Agent 使用课程资料库、题库、错题样例和业务上下文生成结构化输出。

### 讯飞星火 MaaS 层

用于后续垂类问答数据微调、评估和模型能力优化。第一版先沉淀样例数据格式、评估指标和数据生产流程。

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
[课程问答] [错题诊断] [学习规划] [教师分析]  <- 星辰 Agent 层
          |
          v
[星火 MaaS 微调与评估平台]
          |
          v
[课程知识库 / 题库 / 错题库 / 学习画像 / 统计数据]
          |
          v
[MySQL or PostgreSQL / Redis / MinIO / Nginx / Docker Compose]
```
