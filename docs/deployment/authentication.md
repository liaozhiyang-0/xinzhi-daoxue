# 认证基础（第一阶段）

第一阶段提供账号、密码、会话令牌和用户数据归属基础。认证令牌只通过 HttpOnly Cookie 返回；API 响应不会返回明文 access token 或 refresh token。

## 初始化

在 API 虚拟环境中执行增量迁移：

```powershell
.\.venv\Scripts\python.exe -m alembic -c apps/api/alembic.ini upgrade head
```

创建第一个管理账号时使用交互式脚本。密码不会出现在命令行参数、日志或仓库文件中：

```powershell
.\.venv\Scripts\python.exe scripts/create_admin.py --login admin@example.com --display-name 管理员
```

## 生产配置

生产环境必须设置：

```dotenv
APP_ENV=production
AUTH_REQUIRED=true
AUTH_ALLOW_REGISTRATION=false
AUTH_ALLOW_GUEST=true
AUTH_GUEST_SIGNING_KEY=请替换为高强度随机值
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAME_SITE=lax
```

如果前后端跨站部署，需要使用 `AUTH_COOKIE_SAME_SITE=none`，同时保持 `AUTH_COOKIE_SECURE=true`。公开注册关闭后，账号应由管理流程或后续管理系统创建。

开发和测试环境默认保留匿名兼容模式，便于现有本地调试页面继续使用；设置 `AUTH_REQUIRED=true` 后，用户业务接口会要求认证，并以会话账号覆盖请求中的 `user_id`。

## 游客入口

学习端首次进入会提供“登录、注册、游客模式”三种入口。游客模式使用签名 Cookie 生成随机的 `guest_...` 身份，不写入账号表；会话、任务、资料和学习记忆仍按该身份隔离。游客身份只绑定当前浏览器，注册或登录后才适合长期保存和跨设备使用。

接口为 `POST /api/v1/auth/guest`，由 `AUTH_ALLOW_GUEST` 控制。生产环境启用游客模式时必须设置 `AUTH_GUEST_SIGNING_KEY`，并使用高强度随机值；该值不得提交到仓库。

## API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册并建立会话（受 `AUTH_ALLOW_REGISTRATION` 控制） |
| POST | `/api/v1/auth/login` | 登录并轮换会话 Cookie |
| POST | `/api/v1/auth/refresh` | 使用 refresh Cookie 轮换会话 |
| POST | `/api/v1/auth/logout` | 撤销当前会话并清理 Cookie |
| GET | `/api/v1/auth/me` | 获取当前账号和会话信息 |

认证失败、账号停用和登录频率限制会分别返回 401、403 和 429。登录限流当前为进程内实现，后续多实例部署时应替换为共享 Redis 等存储后端。

## 归属边界

启用强制认证后，sessions、tasks、files、memories、learning 和 orchestration 等用户业务接口都会以认证账号作为归属依据。调试接口仅允许管理员访问；Phase 2 将在此基础上补充正式的角色、权限和管理界面。

## 管理接口

第二阶段提供管理员 API，统一位于 `/api/v1/admin`：

- `/overview`：账号、会话和审计概览
- `/accounts`：账号查询、创建、角色/状态修改和密码重置
- `/accounts/{id}/revoke-sessions`：撤销指定账号的全部会话
- `/sessions`：查看和撤销会话
- `/audit-logs`：查询结构化管理与认证审计记录

这些接口始终要求已认证的 `admin` 账号，即使开发环境关闭全局强制认证也不会对匿名请求开放。
