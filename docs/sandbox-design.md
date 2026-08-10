# wasmsh-pyodide-runtime 沙箱集成设计

## 1. 概述

基于 `wasmsh-pyodide-runtime` 为 deepagents 提供 WASM 级别的 Python 代码执行沙箱。Agent 通过 `py_eval` 工具在隔离的 Pyodide（CPython 3.13）环境中执行 Python 代码，支持 numpy、pandas、matplotlib 等数据分析库。

### 核心价值

| 维度 | 能力 |
|------|------|
| **安全隔离** | WASM 虚拟文件系统，无法访问宿主机目录，无法发起系统调用 |
| **网络控制** | `allowed_hosts=[]` — 完全离线，无 SSRF 风险 |
| **包管理** | 通过 `initial_files` + 离线 wheel 缓存，预装 numpy/pandas/matplotlib |
| **文件双向同步** | 宿主机 ↔ 沙箱 VFS 自动同步，agent 无需感知路径差异 |
| **Session 隔离** | 每 session 独立 Node.js 子进程 + 独立 WASM 模块 + 独立 VFS |
| **生命周期管理** | 过期 session 自动清理，防止僵尸进程 |

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI 应用层                            │
│  api/sessions.py        api/stream.py        api/files.py       │
│       │                      │                     │             │
│       ▼                      ▼                     ▼             │
│  ┌────────────┐    ┌──────────────────┐   ┌──────────────┐     │
│  │ evict_session│   │ get_agent()     │   │ 文件上传     │     │
│  └─────┬──────┘    └────────┬─────────┘   └──────┬───────┘     │
│        │                    │                     │              │
│        ▼                    ▼                     ▼              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    AgentPool (agent/ pool.py)            │  │
│  │  _agents: {session_id: (agent, last_access, cleanup_fn)} │  │
│  │  cleanup_fn → _Registry.close() → 杀 Node.js 子进程      │  │
│  └─────────────────────┬────────────────────────────────────┘  │
│                        │                                        │
│                        ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                 build_agent() (agent/engine.py)           │  │
│  │                                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  WasmshInterpreterMiddleware                       │  │  │
│  │  │  ├─ _Registry: {thread_id → _ThreadREPL}           │  │  │
│  │  │  ├─ 自动注入 py_eval 工具                           │  │  │
│  │  │  ├─ before_agent: 恢复 pickle 快照 → 保持 REPL 状态 │  │  │
│  │  │  └─ after_agent:  pickle 当前 globals               │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  CompositeBackend                                  │  │  │
│  │  │  ├─ default: FilesystemBackend → sandboxes/{sid}/  │  │  │
│  │  │  ├─ /skills/: FilesystemBackend (只读)             │  │  │
│  │  │  └─ /.skills/: FilesystemBackend (会话级 skills)   │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ JSON over stdin/stdout
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Node.js 子进程 (每 session 独立)               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Pyodide WASM 模块 (CPython 3.13)             │  │
│  │  ├─ 虚拟文件系统 (EmscriptenFs)                           │  │
│  │  ├─ numpy 2.2.5                                           │  │
│  │  ├─ pandas 2.3.3                                          │  │
│  │  ├─ matplotlib 3.8.4                                      │  │
│  │  └─ wasmsh bash (88 内置命令)                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 核心模块

### 3.1 Sandbox 预加载 (`backend/sandbox/__init__.py`)

负责离线安装 numpy/pandas/matplotlib，无需网络。

```
sandbox_wheels/ (13 个文件, 16.8 MB)
├── numpy-2.2.5-cp313-cp313-pyodide_2025_0_wasm32.whl
├── pandas-2.3.3-cp313-cp313-pyodide_2025_0_wasm32.whl
├── matplotlib-3.8.4-cp313-cp313-pyodide_2025_0_wasm32.whl
├── contourpy, cycler, fonttools, kiwisolver, packaging
├── pillow, pyparsing, python_dateutil, pytz, six
└── (轮子从 jsdelivr CDN 下载，缓存在项目内)
```

**启动流程**：

1. `get_preload_files()` 读取本地 wheel 文件为 `{path: bytes}` 字典
2. 通过 `WasmshSandbox(initial_files=...)` 注入到沙箱 VFS 的 `/wheels/` 下
3. Bootstrap 脚本 (`BOOTSTRAP_SCRIPT`) 用 `zipfile.extractall` 解压到 `/lib/python3.13/site-packages/`
4. 同时强制设置 UTF-8 编码，防止 Windows GBK 导致的 `UnicodeDecodeError`

### 3.2 宿主机 ↔ 沙箱文件同步

wasmsh 沙箱拥有独立的虚拟文件系统（EmscriptenFs），与宿主机文件系统物理隔离。Agent 通过 `FilesystemBackend` 操作宿主文件，通过 `py_eval` 操作沙箱文件——两套文件系统必须同步才能协作。

#### 同步架构

```
                宿主机                           沙箱 VFS
         sandboxes/{session_id}/                 (WASM)
         ┌─────────────────┐             ┌─────────────────┐
   上传  →│ data.csv         │──upload──→│ /data.csv        │
         │ report.xlsx      │──upload──→│ /report.xlsx     │
         │                  │             │                  │
         │ chart.png        │←download──│ /chart.png       │← py_eval 生成
         │ result.json      │←download──│ /result.json     │← py_eval 生成
         └─────────────────┘             └─────────────────┘
```

#### 同步时机

```
沙箱生命周期：

  CREATE ────────────────────────────────────────────────→ CLOSE
    │                                                        │
    │ ① _host_to_sandbox()      每个 py_eval 后              │
    │   upload_files("/{name}")  ┌─────────────────┐        │
    │   - data.csv               │② _sandbox_to_   │       │
    │   - report.xlsx            │   host_raw()    │        │
    │                            │  download_files │ ③ 最终导出
    │                            │  写入 worktree   │        │
    │                            └─────────────────┘        │
```

#### 实现方式：Monkey-Patch

不是通过回调或事件——而是在沙箱创建时直接替换 `execute()` / `aexecute()` / `close()` 方法：

```python
# 保存原始方法引用
_raw_execute = sandbox.execute

# 包装 execute：先执行原逻辑，再导出文件
def _execute_with_export(*args, **kwargs):
    result = _raw_execute(*args, **kwargs)        # 先执行
    _sandbox_to_host_raw(sandbox, worktree, _raw_execute)  # 再导出
    return result

sandbox.execute = _execute_with_export           # 替换
sandbox.aexecute = _aexecute_with_export         # 同上（async版）
sandbox.close = _close_with_export               # 关闭前最终导出
```

中间件的 `py_eval` 工具内部调用 `sandbox.execute()` ——无须改动中间件代码，文件自动同步。

#### 导出细节 (`_sandbox_to_host_raw`)

1. 用原始 `execute`（非 patched 版）执行 `ls -p / | grep -v '/'` 列出沙箱 `/` 下的普通文件
2. 跳过 `bootstrap.py` 和子目录（`wheels/`、`lib/` 等）
3. 调用 `sandbox.download_files(paths)` 获取文件内容
4. 写入宿主 `worktree_root`（即 `sandboxes/{session_id}/`）

**防递归关键**：`_sandbox_to_host_raw` 接受原始 `execute` 函数作为参数，而非调用被 patch 后的 `sandbox.execute`。否则 `_sandbox_to_host_raw → execute → _execute_with_export → _sandbox_to_host_raw → ...` 形成死循环。

#### 路径统一

`working_directory="/"`，upload/download 都用 `/文件名`（非 `/workspace/文件名`）。Agent 在 `py_eval` 中使用 `pd.read_csv('/data.csv')`，在外部工具中使用 `read_file('/data.csv')`——同一路径，无需记忆前缀。

### 3.3 Sandbox 工厂 (`_create_sandbox_factory`)

位于 `backend/agent/engine.py`，返回闭包工厂函数。创建的 sandbox 具备文件同步能力（详见 3.2），并通过 monkey-patch 确保每次 py_eval 后自动导出生成文件。

### 3.4 配置 (`backend/config.py`)

```python
SANDBOX_CONFIG = {
    "step_budget": 100_000,          # VM 步数限制
    "execution_timeout": 60,         # 执行超时（秒）
    "allowed_hosts": [],             # 网络白名单（空=完全离线）
    "max_result_chars": 8000,        # 输出截断长度
    "max_snapshot_bytes": 8 * 1024 * 1024,  # pickle 快照上限
}
```

### 3.5 生命周期管理 (`backend/agent/pool.py`)

```
AgentPool
├─ get_agent(session_id)
│   └─ build_agent() → 返回 (agent, cleanup_fn)
│       cleanup_fn = interpreter._registry.close
│
├─ cleanup_idle(max_idle_seconds=3600)
│   └─ 驱逐过期 agent + 调用 cleanup_fn() → 杀 Node 子进程
│
└─ evict_session(session_id)
    └─ api/sessions.py 删除/归档时调用 → 杀 Node 子进程
```

`cleanup_fn` 为 `None` 时（中间件未启用）安全跳过。

### 3.6 安全措施

| 层级 | 措施 | 说明 |
|------|------|------|
| **WASM 沙箱** | 无 syscall，虚拟 FS | 无法访问宿主机 /etc、/root、C:\ 等 |
| **网络** | `allowed_hosts=[]` | 完全无网络，无法发起 HTTP/SSRF |
| **子进程** | Pyodide 中 `subprocess` 不可用 | 无法 fork/exec |
| **线程** | Pyodide 中 `threading` 不可用 | 无法多线程 |
| **超时** | `asyncio.wait_for(60s)` | 防止 Python 死循环 |
| **步数预算** | `step_budget=100_000` | 限制 shell 命令的 VM 指令数 |
| **Session 隔离** | 独立 Node 进程 + 独立 VFS | 数据/变量不跨 session 泄漏 |

**已知限制**：
- Python 代码不受 `step_budget` 约束（需宿主端 timeout 兜底）
- Shell 和 Python 在同一 WASM 实例内，无进程级隔离
- 仅支持纯 Python wheel，C 扩展需交叉编译为 `wasm32-emscripten`

## 4. 启用 / 禁用

中间件启用/禁用通过 `backend/agent/engine.py` 中的注释控制：

```python
# 启用沙箱：取消以下注释
# interpreter_middleware = WasmshInterpreterMiddleware(
#     sandbox_factory=_create_sandbox_factory(sandboxes_dir),
#     ...
# )
# middleware=[interpreter_middleware],

# 禁用沙箱：保持注释 + middleware 参数不传或为空
middleware=[]   # 或不传该参数
```

**注意**：启用时需同步更新 `MAIN_SYSTEM_PROMPT`，告知 agent 有 `py_eval` 工具可用。

## 5. 依赖

### 5.1 安装方式

wasmsh 沙箱依赖两个 PyPI 包，通过 `pip` 一键安装：

```bash
pip install langchain-wasmsh>=0.7.0
```

`wasmsh-pyodide-runtime` 作为 `langchain-wasmsh` 的传递依赖自动安装，无需手动指定。

```
requirements.txt:
  langchain-wasmsh>=0.7.0        # WasmshSandbox + WasmshInterpreterMiddleware
                                  #   └─ 传递依赖: wasmsh-pyodide-runtime (0.7.0)
```

### 5.2 wasmsh-pyodide-runtime 包内容

安装后在 `site-packages/wasmsh_pyodide_runtime/assets/` 下自动包含：

| 文件 | 大小 | 说明 |
|------|------|------|
| `node-host.mjs` | 12.8 KB | **Node.js 宿主入口**——Python 通过 `subprocess.Popen(["node", "node-host.mjs"])` 启动 |
| `pyodide.asm.wasm` | 14.1 MB | Pyodide WASM 模块：CPython 3.13 + wasmsh bash |
| `pyodide.asm.js` | 2.2 MB | WASM 加载器 + Emscripten 运行时 |
| `pyodide.js` / `pyodide.mjs` | — | Pyodide JS API |
| `python_stdlib.zip` | — | Python 标准库 |
| `pyodide-lock.json` | — | 375 个可安装包的索引（含 numpy/pandas/matplotlib 的 CDN URL） |
| `micropip-0.11.0-py3-none-any.whl` | — | Pyodide 包管理器（wasmsh 环境中不可用，网络层未实现） |
| `lib/` | — | wasmsh JS 运行时模块（文件系统膜、抓取辅助、快照等） |

**总大小**：~36.2 MB（其中 14.1 MB 为 Pyodide WASM 核心）

### 5.3 Node.js 子进程启动原理

```
Python 应用 (FastAPI)
  │
  │ WasmshSandbox.__init__()
  │   → subprocess.Popen(["node", "node-host.mjs"])
  │   → JSON 协议 over stdin/stdout
  │
  ▼
Node.js 子进程 (node-host.mjs)
  │
  │ loadPyodide() → pyodide.asm.wasm
  │   → CPython 3.13 解释器初始化
  │   → wasmsh bash 初始化
  │   → 准备就绪，等待 Python 侧发送指令
  │
  ▼
通信协议:
  Python → Node: {"Run": {"input": "python3 -c 'print(42)'"}}
  Node → Python: {"output": "42", "exit_code": 0}
```

每个 session 启动一个独立的 Node.js 子进程，`WasmshSandbox.close()` 或 Python 进程退出时终止。

### 5.4 运行环境要求

| 组件 | 版本要求 |
|------|---------|
| Node.js | ≥ 20（每 session 一个子进程，RSS ~80MB） |
| Python | 3.11（宿主机，FastAPI 运行环境） |
| 首次冷启动 | ~10-15 分钟（下载并缓存 Pyodide WASM，仅首次） |
| 后续热启动 | ~300ms（WASM 快照恢复） |


## 6. 相关文件

| 文件 | 职责 |
|------|------|
| `backend/sandbox/__init__.py` | wheel 预加载 + bootstrap 脚本 |
| `backend/sandbox_wheels/` | 13 个 Pyodide wheel 缓存 |
| `backend/agent/engine.py` | `_create_sandbox_factory`、`_host_to_sandbox`、`_sandbox_to_host_raw`、中间件集成 |
| `backend/agent/pool.py` | AgentPool 生命周期 + cleanup_fn 管理 |
| `backend/config.py` | `SANDBOX_CONFIG` |
| `backend/api/sessions.py` | session 删除/归档时调用 `agent_pool.evict_session()` |
| `frontend/.../ToolCard.vue` | `py_eval` 工具绿色样式 |
| `frontend/.../MessageList.vue` | `py_eval` → "Python 执行" 展示 |
