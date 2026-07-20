"""FastAPI 应用入口"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from api.sessions import router as sessions_router
from api.files import router as files_router
from stream_handler import router as stream_router
from command_handler import router as command_router
from api.threads import router as threads_router
from agent_pool import agent_pool

_CLEANUP_INTERVAL = 600   # 10 分钟
_CLEANUP_IDLE_SECONDS = 3600  # 1 小时未访问则清理


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：初始化数据库 + 启动 agent 清理任务"""
    init_db()

    async def cleanup_loop():
        while True:
            await asyncio.sleep(_CLEANUP_INTERVAL)
            agent_pool.cleanup_idle(max_idle_seconds=_CLEANUP_IDLE_SECONDS)

    cleanup_task = asyncio.create_task(cleanup_loop())
    yield
    cleanup_task.cancel()


app = FastAPI(title="数据分析 Agent", lifespan=lifespan)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(sessions_router)
app.include_router(files_router)
app.include_router(threads_router)
app.include_router(stream_router)
app.include_router(command_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
