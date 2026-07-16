# 芯智导学：电子信息课程群多智能体平台

## 1. 项目简介

芯智导学面向电子信息课程群，构建以题图识别与分步解题为核心，兼顾课程知识问答、学习反馈、学习规划和教师分析的垂类大模型系统。项目采用“自研教学业务系统 + 科大讯飞星辰 Agent + 星火 MaaS 平台”的混合架构，将课程知识库、题库、学生学习记录和智能体能力结合，为学生提供可追溯的导学服务，为教师提供学情洞察与教学改进建议。

## 2. 第一版目标

第一版聚焦可演示、可验证、可扩展的最小闭环，重点完成识图解题、课程知识问答、学习反馈与简单纠错、学习建议和教师端学情看板。系统暂不追求完整教务系统能力，而是优先打通课程资料组织、Agent 调用、题图解题流程、学习记录沉淀和教师分析展示链路。

## 3. 核心功能

- 题图识别与分步解题：面向电路图、题目截图和图形化课程题目，完成结构提取、方法选择、关键方程和分步计算。
- 课程知识问答：围绕电路理论、模拟电子、数字电子、集成电路等课程知识点回答问题。
- 学习反馈与简单纠错：结合错因标签给出公式适用条件、易错提醒和轻量错因提示。
- 学习规划：结合问答记录、题图解题记录和薄弱知识点生成阶段性复习建议。
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

系统采用分层架构：用户层负责学生和教师入口；前端应用层承载交互页面；自研业务服务层负责账号、课程、题库、学习记录、统计和 Agent 编排；星辰 Agent 层负责识图解题、课程问答、学习规划和教师分析，其中错题诊断能力简化为课程问答内的纠错提示；星火 MaaS 层负责图文解题样例、批量推理、模型评估和后续可选微调；数据与知识层沉淀课程资料、题库、错因标签和学情数据；运维部署层提供容器化和反向代理能力。

## 6. 项目目录说明

```text
docs/              项目定位、范围、架构、路线、演示和团队分工文档
course_materials/  电子信息与集成电路课程群知识库骨架
knowledge_base/    知识库规划、课程目录、题库和错题样例
platform_stack/    识图解题核心定位下的平台工作栈文档
frontend/          前端说明与页面原型
backend/           后端接口与 Agent API 调用设计
database/          数据库设计与初始化 SQL
deploy/            Docker Compose 与 Nginx 部署模板
assets/            图片、截图和演示素材目录
```

课程知识库采用统一结构：

```text
course_materials/
├── 00_knowledge_base_guide.md
├── 01_circuit_theory/
├── ...
├── 25_power_semiconductor_ic/
└── _legacy/
```

每门课程目录包含 `README.md`、`00_course_overview.md`、`chapters/`、`questions/` 和 `wrong_cases/`，用于后续分批建设章节知识、典型题型和错题诊断样例。

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

# 平台工作栈、接口和数据库设计
platform_stack/
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
3. 学生上传题图或电路图，系统调用识图解题 Agent 输出题目识别、电路结构、关键方程、分步计算和易错提醒。
4. 学生追问某一步或提交自己的推导，课程问答 Agent 给出公式条件说明和简单纠错提示。
5. 系统根据问答记录、题图解题记录和错因提示生成学习建议，给出优先知识点、每日任务和掌握检查标准。
6. 教师进入看板查看高频问题、错因标签分布、薄弱知识点和学生活跃度。
7. 教师调用教学建议生成接口，获得课堂讲解、作业补充和后续观察指标建议。

对应文档：

- 学生端原型：`frontend/prototype/student_page.md`
- 教师端原型：`frontend/prototype/teacher_dashboard.md`
- 演示计划：`docs/05_demo_plan.md`
- 后端接口：`backend/api_design.md`
- 平台工作栈：`platform_stack/README.md`

## 9. 课程知识库规划

本项目知识库面向电子信息课程群与集成电路专业方向课程群建设，采用“课程群 → 课程 → 章节 → 知识单元 → 典型题型 → 错题模式 → 学习路径”的组织方式。

课程体系包括：

### 电子信息公共主干课程

- 电路理论
- 模拟电子技术
- 数字电子技术
- 信号与系统
- 数字信号处理
- 通信原理
- 高频电子线路
- 电磁场与电磁波
- 信息论与编码
- 嵌入式系统

### 集成电路专业核心课程

- 半导体物理
- 半导体器件 / 微电子器件
- 集成电路制造工艺
- CMOS 数字集成电路设计
- 模拟集成电路设计
- 数字集成电路设计 / ASIC 设计基础
- 集成电路版图设计
- 集成电路测试
- 先进封装与测试
- EDA 技术与芯片设计流程
- Verilog / SystemVerilog
- FPGA 与数字系统设计
- 片上系统 SoC 设计
- 射频集成电路设计
- 功率半导体与功率集成电路

知识库规划文件位于 `knowledge_base/`，课程资料骨架位于 `course_materials/`。当前阶段只建立目录和模板，不展开具体课程知识。

## 10. 当前开发阶段

当前处于项目初始化与方案设计阶段，已完成基础仓库结构、项目文档、课程知识库骨架、Agent 设计、接口设计、数据库设计和部署模板。后续开发应以第一版闭环为边界，优先完成可演示的端到端流程。

## 11. 后续计划

1. 优先补充 P0 课程的课程总览、章节目录、典型题型框架和错题模式框架。
2. 将 `_legacy/` 中可复用的旧知识点资料逐步迁移到新的课程知识库结构。
3. 接入星辰 Agent 并验证识图解题、课程问答、规划和分析链路。
4. 实现前端学生端与教师端原型页面。
5. 实现业务后端 API、数据存储和统计逻辑。
6. 构建 MaaS 图文解题样例、批量推理与离线评估流程。
7. 准备演示数据、答辩材料和部署环境。

---

## 12. 本地阶段 0—1.5 工程基线

本仓库用于建设“芯智导学”电子信息课程群多智能体平台。原有轻量 MVP 所积累的课程知识库、Prompt、测试案例、演示资料和只读历史资料继续保留；当前新增阶段 0—1 的本地工程基线，不推翻已经在讯飞星辰平台跑通的 `SOLVER_CT_电路理论专业解题_v1.0`。

## 当前完成阶段

- 阶段 0：冻结 SOLVER_CT v1.0 基线、性能观测、节点清单模板、已知问题、发布清单与回归评测结构。
- 阶段 1：建立 FastAPI API 壳层、统一 Agent 协议、Mock Provider、星辰未发布边界、数据库模型、文件存储、Docker Compose、脚本、测试与 CI。
- 阶段 1.5：任务创建改为 HTTP 202 非阻塞模式，增加 TaskRunner、递增事件 sequence、SSE 重连、取消、重试、调试页、评测脚手架、请求 ID 和敏感文件扫描。
- `SOLVER_CT` 尚未发布外部 API。本阶段不会发起真实星辰 HTTP 请求，也不要求填写星辰 API 配置。

总体架构见 `docs/architecture/02_xinzhi_multi_agent_platform_plan_v1.0.md`。

## 目录结构

```text
apps/
  api/                       FastAPI、SQLAlchemy、Alembic 与测试
  worker/                    后续异步 Worker 预留
agent_configs/
  registry.yaml              Agent 注册表
  course_packs/              课程包配置
  workflows/                 工作流元数据
docs/
  architecture/              总体架构
  baseline/                  SOLVER_CT 冻结基线
  deployment/                本地开发说明
evaluation/circuit_theory/   电路理论回归评测结构
scripts/                     Windows 与 Linux/macOS 脚本
archive_legacy/              原有历史资料，只读保留
.local_inputs/               本地原始输入，Git/Docker 忽略
.local_outputs/              本地日志与验证输出，Git/Docker 忽略
```

仓库中已有的课程资料、知识库、题库和用户新增中文资料目录不属于阶段 0—1 的重写范围。

## 环境要求

- Windows 11 PowerShell 或 Linux/macOS shell。
- 推荐 Python 3.11 或 3.12。
- Docker Desktop 或 Docker Engine + Compose v2。
- Git 和 GitHub CLI（仅发布时需要）。

## Windows PowerShell 启动

如系统限制脚本执行，优先只对当前 PowerShell 进程放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\dev.ps1
```

脚本会创建 `.venv`、安装依赖、从 `.env.example` 创建 `.env`、启动 PostgreSQL/Redis/MinIO、执行 Alembic migration 并启动 API。

## Docker Compose 启动

Windows 可直接使用自动适配脚本。它会在缺少 Docker Desktop 时通过
winget 安装、启动 Docker Engine、创建 `.env`、校验 Compose、构建镜像并等待
全部服务健康：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\docker_dev.ps1
```

停止服务但保留数据卷：

```powershell
.\scripts\docker_down.ps1
```

也可以手动执行：

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up -d --build --wait
```

开发默认密码只用于本机，部署到共享环境前必须修改。

## 手动启动 API

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
Copy-Item .env.example .env
Set-Location apps/api
$env:DATABASE_URL="postgresql+asyncpg://xzd_user:xzd_password@localhost:5432/xzd"
$env:REDIS_URL="redis://localhost:6379/0"
$env:MINIO_ENDPOINT="localhost:9000"
..\..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ../..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload
```

## 测试与代码质量

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
.\.venv\Scripts\python.exe -m pytest
```

或运行：

```powershell
.\scripts\check.ps1
```

CI 使用 Python 3.12、SQLite 与 Mock Provider，不读取真实星辰秘密。

## API

- 健康检查：`http://localhost:8000/health`
- v1 健康检查：`http://localhost:8000/api/v1/health`
- Swagger：`http://localhost:8000/docs`
- 本地调试台：`http://localhost:8000/debug`
- OpenAPI：`http://localhost:8000/openapi.json`

主要接口：

```text
POST /api/v1/sessions
GET  /api/v1/sessions/{session_id}
POST /api/v1/tasks
GET  /api/v1/tasks/{task_id}
GET  /api/v1/tasks/{task_id}/events
GET  /api/v1/tasks/{task_id}/stream
POST /api/v1/tasks/{task_id}/retry
POST /api/v1/tasks/{task_id}/cancel
POST /api/v1/files
GET  /api/v1/files/{file_id}
GET  /api/v1/artifacts/{artifact_id}
GET  /debug
```

## Mock Provider

`.env` 默认配置：

```env
DEFAULT_AGENT_PROVIDER=mock
ALLOW_MOCK_FALLBACK=true
XINGCHEN_ENABLED=false
```

Mock 结果始终包含 `provider=mock` 和 `mock_result` 警告，不代表真实星辰输出，适用于本地开发、测试和演示。

## 星辰 Provider 状态

当前统一状态：

```text
publication_status: not_published
runtime_available: false
```

`XingchenCloudProvider` 当前只保留接口边界并抛出 `NotPublishedError`，代码不会构造或发送真实 HTTP 请求。`.env.example` 中的星辰字段只是未来占位，本阶段无需填写。

## 数据库迁移

```powershell
.\scripts\init_db.ps1
```

或：

```powershell
Set-Location apps/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

## 安全说明

- `.env` 已被 `.gitignore` 忽略，只提交 `.env.example`。
- 不在代码和 Compose 文件中保存真实 API Key 或生产密码。
- 日志不输出完整 API Key、数据库密码或默认完整学生隐私数据。
- 上传文件只允许 png、jpg、jpeg、pdf、md、txt，不执行上传内容。
- 上传同时校验扩展名、MIME、空文件、大小、路径穿越和 SHA-256。
- 原始星辰 YAML 只允许放入 `.local_inputs/`，不得提交。
- 本地默认密码必须在共享部署前修改。

## 当前未实现

- 真实讯飞星辰协议和 SOLVER_CT 云端调用。
- 原始 YAML 的真实 SHA-256、节点数和连线数（本轮附件未提供 YAML）。
- 用户所述完整总体架构原文恢复（本轮附件未提供原文）。
- 完整 LangGraph、多智能体编排和 RAGFlow。
- Celery/分布式 Worker。
- 完整学生端、教师端、科研端。
- Kubernetes。

## 后续阶段

1. 工作流发布后接入真实 `SOLVER_CT`。
2. 完成本地到星辰的端到端调用与真实回归测试。
3. 在现有 `/debug` 基础上迭代最小调试页面。
4. 开始 `LEARN_01` 课程知识问答。
