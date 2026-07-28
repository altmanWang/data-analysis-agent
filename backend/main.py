"""FastAPI 应用入口"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 配置日志：INFO 级别以上输出到控制台
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from db import init_db
from config import CLEANUP_CONFIG
from api.sessions import router as sessions_router
from api.files import router as files_router
from api.stream import router as stream_router
from api.commands import router as command_router
from api.threads import router as threads_router
from api.agents import router as agents_router, session_router as session_agent_router
from agent.pool import agent_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：初始化数据库 + 启动 agent 清理任务"""
    init_db()

    async def cleanup_loop():
        while True:
            await asyncio.sleep(CLEANUP_CONFIG["interval_seconds"])
            agent_pool.cleanup_idle(max_idle_seconds=CLEANUP_CONFIG["idle_timeout_seconds"])

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
app.include_router(agents_router)
app.include_router(session_agent_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
