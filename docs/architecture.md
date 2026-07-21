# data-analysis-agent 系统架构

> 更新日期: 2026-07-20

---

## 图例

| 标记 | 含义 |
|------|------|
| ✅ 实线框 | 已实现 |
| 🔶 虚线框 | 部分实现 (打桩/占位) |
| ❌ 红色虚线框 | 未实现 (规划中) |
| ── 实线箭头 | 已实现的数据流 |
| - - 虚线箭头 | 规划中/打桩的数据流 |

---

## 一、整体系统架构

```mermaid
graph TB
    subgraph CLIENT["🖥️ 客户端层"]
        Browser["Vue 3 前端<br/>localhost:5173"]
    end

    subgraph AUTH["🔐 认证授权层 ❌ 未实现"]
        direction LR
        AuthGW["API Gateway / 认证中间件 ❌"]
        JWT["JWT Token 验证 ❌"]
        RBAC["租户权限校验 ❌"]
        Quota["资源配额管理 ❌"]
        AuthGW --> JWT
        AuthGW --> RBAC
        AuthGW --> Quota
    end

    subgraph API["📡 API 层 (FastAPI)"]
        direction LR
        SessionAPI["/api/sessions ✅<br/>会话 CRUD + 归档"]
        FileAPI["/api/sessions/{id}/files ✅<br/>上传/预览/删除"]
        ThreadAPI["/api/threads/{id}/* ✅<br/>state/messages/history"]
        StreamSSE["/api/threads/{id}/stream ✅<br/>SSE 流式 Agent 输出"]
        CommandAPI["/api/threads/{id}/commands 🔶<br/>Protocol v2 命令<br/>run.start ✅ / input.respond 🔶"]
        HealthAPI["/health ✅"]
    end

    subgraph SERVICE["⚙️ 服务层"]
        direction LR
        SM["SessionManager ✅<br/>会话 CRUD (MySQL)"]
        WM["WorktreeManager 🔶<br/>沙盒管理<br/>本地创建/删除 ✅<br/>OBS 归档/恢复 🔶"]
        AP["AgentPool ✅<br/>懒加载缓存<br/>定时清理过期实例"]
    end

    subgraph AGENT["🤖 Agent 层"]
        direction LR
        AE["agent_engine.build_agent() ✅<br/>deepagents 工厂"]
        DA["data-analyst 子代理 ✅<br/>load_csv → execute_python → HTML报告"]
        Tools["tools/data_tools.py ✅<br/>load_csv / load_excel / execute_python"]
        Skills["skills/ ✅<br/>ui-ux-pro-max (HTML美化)"]
    end

    subgraph STORAGE["💾 存储层"]
        direction LR
        Sandbox["本地沙盒 ✅<br/>sandboxes/{session_id}/<br/>临时文件 + Agent产出"]
        OBS["OBS 对象存储 🔶<br/>❌ 归档/恢复: 打桩<br/>❌ 长期持久化: 未实现"]
        DB["MySQL 8 ✅<br/>5张表"]
    end

    subgraph DB_TABLES["🗄️ 数据库 (MySQL)"]
        direction LR
        Sessions["sessions ✅<br/>会话元数据<br/>user_id 字段已预留"]
        MsgHist["message_history ✅<br/>对话历史<br/>含 thinking/tool 角色"]
        CP["checkpoints ✅"]
        CPW["checkpoint_writes ✅"]
        CPB["checkpoint_blobs ✅"]
    end

    subgraph EXTERNAL["🌐 外部服务"]
        LLM["DeepSeek API ✅<br/>deepseek-v4-flash"]
    end

    %% 连接线
    Browser -->|"HTTP REST + SSE"| API
    Browser -.->|"❌ 未来: 经认证层"| AUTH
    AUTH -.-> API

    API --> SERVICE
    SessionAPI --> SM
    FileAPI --> WM
    StreamSSE --> AP
    CommandAPI --> SM
    ThreadAPI --> DB

    SERVICE --> AGENT
    AP --> AE
    AE --> DA
    AE --> Tools
    AE --> Skills

    SERVICE --> DB
    SM --> Sessions
    SM --> MsgHist
    AP --> CP

    AGENT --> STORAGE
    Tools --> Sandbox
    DA --> Sandbox

    WM --> Sandbox
    WM -.->|"🔶 打桩"| OBS

    AGENT --> EXTERNAL
    AE --> LLM

    %% 样式
    style AUTH fill:#fff0f0,stroke:#ff4444,stroke-dasharray:5
    style OBS fill:#fff8e0,stroke:#e6a700,stroke-dasharray:5
    style WM fill:#fff8e0,stroke:#e6a700,stroke-dasharray:3
    style CommandAPI fill:#fff8e0,stroke:#e6a700,stroke-dasharray:3
```

---

## 二、认证授权详细架构 ❌ 全部未实现

```mermaid
graph TB
    subgraph CURRENT["当前状态: 无认证"]
        direction LR
        C1["API 端点"]
        C2["user_id 从 query string 传入<br/>❌ 可被伪造"]
        C3["session_manager.get()<br/>❌ 不校验归属"]
        C1 --> C2 --> C3
    end

    subgraph TARGET["目标状态: JWT + 租户隔离"]
        direction TB
        
        Login["POST /auth/login ✅ 需实现<br/>返回 JWT access_token"]
        
        subgraph MW["FastAPI Middleware / Depends ❌"]
            JWTVerify["验证 JWT Token"]
            ExtractTenant["提取 tenant_id + user_id"]
            InjectContext["注入 RequestContext<br/>tenant_id, user_id, roles"]
        end
        
        subgraph AuthZ["授权层 ❌"]
            TenantFilter["所有 DB 查询强制带 tenant_id"]
            ResourceCheck["session_id 归属校验"]
            RateLimit["按租户限流"]
            QuotaCheck["按租户资源配额<br/>沙盒数/磁盘/并发"]
        end
        
        subgraph API2["API 端点 (改造后)"]
            SecureAPI["所有端点从 RequestContext<br/>获取 tenant_id/user_id<br/>不再信任客户端参数"]
        end
        
        Login --> MW
        MW --> AuthZ
        AuthZ --> API2
    end

    style CURRENT fill:#fff0f0,stroke:#ff4444
    style MW fill:#fff0f0,stroke:#ff4444,stroke-dasharray:5
    style AuthZ fill:#fff0f0,stroke:#ff4444,stroke-dasharray:5
```

### 改造要点

| 改造项 | 当前 | 目标 | 涉及文件 |
|--------|------|------|----------|
| 用户认证 | ❌ 无 | JWT + refresh token | 新增 `backend/auth/` |
| 租户隔离 | ❌ user_id 可伪造 | 所有查询加 `WHERE tenant_id = ?` | `session_manager.py`, `api/threads.py`, `api/files.py` |
| API 保护 | ❌ 全开放 | Depends(get_current_user) | `api/*.py`, `stream_handler.py`, `command_handler.py` |
| 会话权限 | ❌ 知道 ID 就能访问 | 校验 `session.tenant_id == request.tenant_id` | `session_manager.py` |
| 资源配额 | ❌ 无限制 | 按租户限制会话数、磁盘、并发 | 新增 `backend/quota.py` |

---

## 三、存储架构 (本地 + OBS)

```mermaid
graph LR
    subgraph UPLOAD["📤 用户上传"]
        CSV["CSV/Excel 文件"]
    end

    subgraph LOCAL["💻 本地存储 ✅"]
        SandboxDir["sandboxes/{session_id}/<br/>├── 用户上传文件<br/>├── Agent 生成的 HTML/PNG<br/>└── tmp/ 临时数据"]
    end

    subgraph OBS_CLOUD["☁️ OBS 对象存储"]
        Archive["会话归档 🔶 打桩<br/>worktree_manager.archive_session()<br/>→ 本地打包 zip<br/>→ TODO: OBS 上传"]
        Restore["会话恢复 🔶 打桩<br/>worktree_manager.restore_session()<br/>→ TODO: OBS 下载<br/>→ 本地解压"]
        Persist["长期持久化 ❌ 未实现<br/>会话结束后自动上传<br/>本地沙盒定期清理"]
    end

    subgraph LIFECYCLE["🔄 文件生命周期"]
        direction TB
        Create["1. 会话创建 → 本地沙盒 ✅"]
        Active["2. 活跃期 → Agent 读写本地 ✅"]
        Idle["3. 闲置 → 本地沙盒保留 ✅"]
        Archive2["4. 归档 → 打包 zip + OBS 上传 🔶"]
        Delete["5. 软删除 → 清理本地 + DB 数据 ✅"]
        Restore2["6. 恢复 → OBS 下载 + 本地解压 🔶"]
    end

    UPLOAD --> SandboxDir
    SandboxDir -.->|"🔶 打桩"| Archive
    Archive --> OBS_CLOUD
    OBS_CLOUD -.->|"🔶 打桩"| Restore
    Restore --> SandboxDir
    SandboxDir -.->|"❌ 未实现"| Persist
    Persist --> OBS_CLOUD

    style OBS_CLOUD fill:#fff8e0,stroke:#e6a700,stroke-dasharray:5
    style Archive fill:#fff8e0,stroke:#e6a700,stroke-dasharray:3
    style Restore fill:#fff8e0,stroke:#e6a700,stroke-dasharray:3
    style Persist fill:#fff0f0,stroke:#ff4444,stroke-dasharray:5
```

### OBS 集成状态

| 功能 | 状态 | 实现文件 | 备注 |
|------|------|----------|------|
| 会话归档 (archive) | 🔶 打桩 | `worktree_manager.py:100-120` | 本地 zip 打包完成，OBS 上传为 `logger.info("[OBS打桩]")` |
| 会话恢复 (restore) | 🔶 打桩 | `worktree_manager.py:122-140` | 仅检查本地 zip 是否存在，OBS 下载未实现 |
| `obs_archive_key` 记录 | ✅ | `session_manager.py:120-129` | DB 字段已就绪 |
| 会话结束时自动归档 | ❌ | — | 需在 `soft_delete()` 或定时任务中触发 |
| 长期持久化 | ❌ | — | 活跃会话数据仍在本地，无异地备份 |
| OBS SDK 集成 | ❌ | — | 需引入 `boto3` 或华为云 OBS SDK |

---

## 四、数据流 (全链路)

```mermaid
sequenceDiagram
    participant U as 用户 (浏览器)
    participant FE as Vue 3 前端
    participant Auth as 认证层 ❌
    participant API as FastAPI
    participant Svc as 服务层
    participant Agent as Agent 层
    participant LLM as DeepSeek
    participant FS as 本地沙盒
    participant OBS as OBS 存储 🔶
    participant DB as MySQL

    Note over U,DB: ─── 当前已实现 ───

    U->>FE: 上传 CSV 文件
    FE->>API: POST /api/sessions/{id}/files
    API->>Svc: worktree_manager
    Svc->>FS: 写入 sandboxes/{sid}/
    Svc-->>FE: 上传成功 ✅

    U->>FE: 发送分析指令
    FE->>API: POST /api/threads/{id}/stream (SSE)
    API->>Svc: agent_pool.get_agent()
    Svc->>Agent: agent.astream_events(v3)
    Agent->>LLM: 调用 DeepSeek
    Agent->>FS: 读取 CSV / 写入 HTML 报告
    Agent-->>API: SSE 事件流 (thinking/text/tool/done)
    API-->>FE: SSE 事件流
    FE-->>U: 实时渲染 ✅

    API->>DB: 异步保存消息到 message_history ✅

    Note over U,DB: ─── 打桩/未实现 ───

    U->>FE: 归档会话
    FE->>API: POST /api/sessions/{id}/archive
    API->>Svc: worktree_manager.archive_session()
    Svc->>FS: 打包为 zip
    Svc-->>OBS: [打桩] 模拟上传 🔶
    Svc->>DB: 更新 obs_archive_key 🔶
    Svc->>FS: 清理本地沙盒 ✅
```

---

## 五、数据库 ER 图

```mermaid
erDiagram
    sessions {
        VARCHAR36 session_id PK "UUID"
        VARCHAR200 title "会话标题"
        VARCHAR100 user_id "用户标识 (已预留, 未来关联 tenants)"
        VARCHAR500 worktree_path "沙盒路径"
        VARCHAR500 obs_archive_key "OBS 归档 key 🔶"
        VARCHAR20 status "状态机: active/archiving/archived/deleted"
        DATETIME created_at
        DATETIME last_active
    }
    
    tenants {
        VARCHAR36 tenant_id PK "❌ 未建表"
        VARCHAR100 name "❌"
        VARCHAR500 llm_api_key "❌ 租户级 LLM key"
        VARCHAR100 llm_model "❌"
        INT max_sessions "❌ 配额"
        BIGINT max_disk_bytes "❌ 磁盘配额"
    }

    message_history {
        BIGINT id PK
        VARCHAR36 session_id FK
        VARCHAR16 role "user/assistant/tool"
        LONGTEXT content
        LONGTEXT thinking_content
        VARCHAR128 tool_name
        JSON tool_args
        JSON tool_result
        VARCHAR16 tool_status
        DATETIME created_at
    }

    checkpoints {
        BIGINT id PK
        VARCHAR128 thread_id "对应 session_id"
        VARCHAR128 checkpoint_id
        VARCHAR128 parent_checkpoint_id
        LONGBLOB checkpoint
    }

    sessions ||--o{ message_history : "1:N"
    sessions ||--o{ checkpoints : "1:N (thread_id)"
    tenants ||--o{ sessions : "1:N ❌ 未实现"
```

---

## 六、实现状态总览

| 模块 | 子功能 | 状态 | 优先级 |
|------|--------|------|--------|
| **认证** | JWT 登录 | ❌ | P0 |
| | Token 刷新 | ❌ | P0 |
| | 租户上下文注入 | ❌ | P0 |
| **授权** | 会话归属校验 | ❌ | P0 |
| | API 端点保护 | ❌ | P0 |
| | 资源配额 | ❌ | P1 |
| **存储** | 本地沙盒创建/删除 | ✅ | — |
| | 文件上传/预览 | ✅ | — |
| | OBS 归档 (上传) | 🔶 | P1 |
| | OBS 恢复 (下载) | 🔶 | P1 |
| | 自动持久化 | ❌ | P2 |
| **Agent** | deepagents 工厂 | ✅ | — |
| | Agent 缓存池 | ✅ | — |
| | data-analyst 子代理 | ✅ | — |
| | SSE 流式输出 (v3) | ✅ | — |
| **会话** | CRUD | ✅ | — |
| | 软删除 + 级联清理 | ✅ | — |
| | 归档/恢复 | 🔶 | P1 |
| **协议** | Protocol v2 类型 | ✅ | — |
| | /stream SSE 端点 | ✅ | — |
| | /commands 端点 | 🔶 | P2 |
| **数据库** | sessions 表 | ✅ | — |
| | message_history 表 | ✅ | — |
| | checkpointer 三表 | ✅ | — |
| | tenants 表 | ❌ | P0 |
| | tenant_api_keys 表 | ❌ | P1 |

---

## 七、依赖关系

```
Python 依赖 (requirements.txt):
├── fastapi==0.115.12        ← Web 框架
├── langgraph>=1.0.5         ← Agent 状态图
├── langchain>=1.2.0         ← LLM 工具链
├── deepagents>=0.6.0        ← Agent 工厂 (CompositeBackend + skills)
├── pymysql                  ← MySQL 驱动
├── pandas + openpyxl        ← 数据分析
├── matplotlib               ← 图表生成
├── uvicorn[standard]        ← ASGI 服务器
├── python-multipart + aiofiles ← 文件上传
├── python-dotenv            ← 环境变量
└── langchain-openai         ← DeepSeek 适配 (OpenAI 兼容)

前端依赖 (package.json):
├── vue@3                    ← UI 框架
├── vue-router@4             ← 路由
├── pinia@4                  ← 状态管理
├── @microsoft/fetch-event-source ← SSE 客户端
├── marked                   ← Markdown 渲染
└── highlight.js             ← 代码语法高亮
```
