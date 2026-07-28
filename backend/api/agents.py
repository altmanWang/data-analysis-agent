# backend/api/agents.py
"""REST API: Agent 管理与会话关联"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent_service import agent_service

router = APIRouter(prefix="/api/agents", tags=["agents"])

# ────────── 请求模型 ──────────


class CreateAgentRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(..., max_length=50000)


class UpdateAgentRequest(BaseModel):
    name: str = Field(..., max_length=100)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(..., max_length=50000)


class SelectAgentRequest(BaseModel):
    agent_id: int


# ────────── Agent CRUD ──────────


@router.get("")
async def list_agents(user_id: str = ""):
    """获取所有 Agent 列表"""
    return agent_service.list_all(user_id=user_id)


@router.post("")
async def create_agent(body: CreateAgentRequest, user_id: str = ""):
    """创建自定义 Agent"""
    try:
        agent = agent_service.create(
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
            user_id=user_id,
        )
        return agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建失败: {str(e)}")


@router.get("/{agent_id}")
async def get_agent(agent_id: int):
    """获取单个 Agent 详情"""
    agent = agent_service.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent


@router.put("/{agent_id}")
async def update_agent(agent_id: int, body: UpdateAgentRequest):
    """更新 Agent"""
    agent = agent_service.update(agent_id, body.name, body.description, body.system_prompt)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return agent


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int):
    """删除 Agent"""
    success = agent_service.delete(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return {"message": "已删除"}


# ────────── Session-Agent 关联 ──────────
session_router = APIRouter(prefix="/api/sessions/{session_id}/agent", tags=["session-agent"])


@session_router.get("")
async def get_session_agents(session_id: str):
    """获取当前 session 选中的所有 Agent"""
    agents = agent_service.get_session_agents(session_id)
    return {"session_id": session_id, "agents": agents}


@session_router.post("")
async def toggle_session_agent(session_id: str, body: SelectAgentRequest):
    """切换 session 的 Agent（已选则移除，未选则添加）"""
    result = agent_service.toggle_session_agent(session_id, body.agent_id)
    return {"session_id": session_id, "added": result["added"], "agents": result["agents"]}


@session_router.delete("")
async def clear_session_agents(session_id: str):
    """清空 session 的所有 Agent 选择"""
    agent_service.remove_session_agents(session_id)
    return {"message": "已清空"}
