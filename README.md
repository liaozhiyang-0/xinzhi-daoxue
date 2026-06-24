# 芯智导学：电子信息课程群垂类大模型系统

## 1. 项目简介

芯智导学面向电子信息课程群，构建集智能答疑、错题诊断、学习建议和学情分析于一体的垂类大模型系统。项目采用“自研教学业务系统 + 科大讯飞星辰 Agent + 星火 MaaS 微调平台”的混合架构，将课程知识库、题库、学生学习记录和智能体能力结合，为学生提供可追溯的导学服务，为教师提供学情洞察与教学改进建议。

## 2. 第一版目标

第一版聚焦可演示、可验证、可扩展的最小闭环，重点完成学生智能答疑、错题诊断、学习建议和教师端学情看板。系统暂不追求完整教务系统能力，而是优先打通课程资料组织、Agent 调用、学习记录沉淀和教师分析展示链路。

## 3. 核心功能

- 学生智能答疑：围绕模拟电子、数字电子、集成电路等课程知识点回答问题。
- 错题诊断：根据学生提交的题目、答案和标准答案识别错误原因。
- 学习建议：结合错题记录和薄弱知识点生成阶段性复习建议。
- 教师端学情看板：展示高频问题、错题类型、薄弱知识点和活跃度统计。
- 教学建议生成：基于班级学情为教师生成教学改进建议。

## 4. 技术路线

```text
前端：Vue3 + TypeScript + Element Plus + ECharts
业务后端：Spring Boot / FastAPI
智能体开发：科大讯飞星辰 Agent 开发平台
模型训练：科大讯飞星火 MaaS 大模型微调平台
数据库：MySQL / PostgreSQL
缓存：Redis
文件存储：MinIO
部署：Docker Compose，后续支持 Kubernetes
协作平台：语雀 + GitHub
```

## 5. 系统架构

系统采用分层架构：用户层负责学生和教师入口；前端应用层承载交互页面；自研业务服务层负责账号、课程、题库、学习记录、统计和 Agent 编排；星辰 Agent 层负责课程问答、错题诊断、学习规划和教师分析；星火 MaaS 层负责后续垂类数据微调；数据与知识层沉淀课程资料、题库、错题和学情数据；运维部署层提供容器化和反向代理能力。

## 6. 项目目录说明

```text
docs/              项目定位、范围、架构、路线、演示和团队分工文档
course_materials/  电子信息课程群知识点资料
knowledge_base/    知识点目录、题库和错题样例
agent_design/      星辰 Agent 设计文档
maas_training/     MaaS 微调数据格式、样例和评估方案
frontend/          前端说明与页面原型
backend/           后端接口与 Agent API 调用设计
database/          数据库设计与初始化 SQL
deploy/            Docker Compose 与 Nginx 部署模板
assets/            图片、截图和演示素材目录
```

## 7. 快速开始

### 7.1 克隆仓库

```bash
git clone https://github.com/liaozhiyang-0/xinzhi-daoxue.git
cd xinzhi-daoxue
```

### 7.2 准备环境变量

```bash
cp .env.example .env
```

请只在本地 `.env` 中填写数据库、Redis、MinIO、星辰 Agent 和星火 MaaS 的真实配置，不要将 `.env` 提交到 Git。

### 7.3 查看项目文档

```bash
# 项目定位与范围
docs/01_project_positioning.md
docs/02_first_version_scope.md

# 系统架构与技术路线
docs/03_system_architecture.md
docs/04_technical_route.md

# Agent、接口和数据库设计
agent_design/
backend/api_design.md
database/database_schema.md
```

### 7.4 初始化数据库结构

第一版优先使用 MySQL。数据库建表语句位于：

```bash
database/init.sql
```

示例执行方式：

```bash
mysql -h localhost -P 3306 -u root -p xinzhi_daoxue < database/init.sql
```

### 7.5 部署模板

部署模板位于 `deploy/docker-compose.yml`。当前前后端工程仍是设计阶段，Compose 文件主要用于描述服务关系，真实镜像和启动命令需在代码实现后补齐。

## 8. 第一版演示链路

第一版演示围绕“学生学习闭环 + 教师学情反馈”展开：

1. 学生选择课程和知识点，例如“模拟电子技术 / MOS 管工作区”。
2. 学生在智能问答区输入问题，系统调用课程问答 Agent 返回概念、公式、步骤和易错点。
3. 学生提交错题，包括题目、学生答案和参考答案，系统调用错题诊断 Agent 识别错误类型。
4. 系统根据问答记录和错题记录生成学习建议，给出优先知识点、每日任务和掌握检查标准。
5. 教师进入看板查看高频问题、错题类型分布、薄弱知识点和学生活跃度。
6. 教师调用教学建议生成接口，获得课堂讲解、作业补充和后续观察指标建议。

对应文档：

- 学生端原型：`frontend/prototype/student_page.md`
- 教师端原型：`frontend/prototype/teacher_dashboard.md`
- 演示计划：`docs/05_demo_plan.md`
- 后端接口：`backend/api_design.md`

## 9. 当前开发阶段

当前处于项目初始化与方案设计阶段，已完成基础仓库结构、项目文档、课程资料模板、Agent 设计、接口设计、数据库设计和部署模板。后续开发应以第一版闭环为边界，优先完成可演示的端到端流程。

## 10. 后续计划

1. 完成课程资料和题库的结构化整理。
2. 接入星辰 Agent 并验证问答、诊断、规划和分析链路。
3. 实现前端学生端与教师端原型页面。
4. 实现业务后端 API、数据存储和统计逻辑。
5. 构建 MaaS 微调数据集与离线评估流程。
6. 准备演示数据、答辩材料和部署环境。
