# backend/api/skills.py
"""REST API: Skill 上传/管理 + Agent-Skill 绑定"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from services.skill_service import skill_service

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SetSkillsRequest(BaseModel):
    skill_ids: list[int] = []


# ────────── Skill CRUD ──────────

@router.post("/upload")
async def upload_skill(file: UploadFile = File(...), user_id: str = ""):
    """上传 zip 技能包"""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持 .zip 文件")
    try:
        zip_bytes = await file.read()
        skill = skill_service.upload_and_install(zip_bytes, user_id=user_id)
        return skill
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.get("")
async def list_skills(user_id: str = ""):
    """获取所有已安装的技能列表"""
    return skill_service.list_all(user_id=user_id)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: int):
    """删除技能包"""
    ok = skill_service.delete(skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return {"message": "已删除"}


# ────────── Agent-Skill 绑定 ──────────
agent_skill_router = APIRouter(prefix="/api/agents/{agent_id}/skills", tags=["agent-skills"])


@agent_skill_router.get("")
async def get_agent_skills(agent_id: int):
    """获取指定 Agent 绑定的 Skills"""
    return skill_service.get_agent_skills(agent_id)


@agent_skill_router.put("")
async def set_agent_skills(agent_id: int, body: SetSkillsRequest):
    """全量设置 Agent 的 Skills"""
    skill_service.set_agent_skills(agent_id, body.skill_ids)
    return {"message": "已更新"}
