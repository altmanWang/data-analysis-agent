"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from api.sessions import router as sessions_router
from api.files import router as files_router
from stream_handler import router as stream_router
from command_handler import router as command_router
from api.threads import router as threads_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    init_db()
    yield


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
