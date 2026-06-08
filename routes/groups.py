from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import List
from services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["Groups"])

class GroupConfigPayload(BaseModel):
    home_group_id: int
    source_group_ids: List[int]
    blacklist: List[int] = []

def get_group_service(request: Request) -> GroupService:
    return request.app.state.group_service

@router.get("/")
async def list_groups(service: GroupService = Depends(get_group_service)):
    groups = await service.fetch_groups()
    return {"groups": groups}

@router.post("/config")
async def update_config(payload: GroupConfigPayload, service: GroupService = Depends(get_group_service)):
    service.set_config(payload.home_group_id, payload.source_group_ids, payload.blacklist)
    return {"status": "success", "message": "Configuration updated"}