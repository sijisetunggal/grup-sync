from fastapi import APIRouter, Depends, Request, HTTPException
from services.sync_service import SyncService

router = APIRouter(prefix="/sync", tags=["Sync"])

def get_sync_service(request: Request) -> SyncService:
    return request.app.state.sync_service

@router.post("/start")
async def start_sync(service: SyncService = Depends(get_sync_service)):
    if not service.group_service.home_group_id:
        raise HTTPException(status_code=400, detail="Home group not configured")
    if not service.group_service.source_group_ids:
        raise HTTPException(status_code=400, detail="Source groups not configured")
        
    started = await service.start_sync()
    if not started:
        raise HTTPException(status_code=409, detail="Sync already running")
    return {"status": "success", "message": "Sync started"}

@router.post("/stop")
async def stop_sync(service: SyncService = Depends(get_sync_service)):
    await service.stop_sync()
    return {"status": "success", "message": "Sync stopped"}

@router.get("/stats")
async def get_stats(service: SyncService = Depends(get_sync_service)):
    return service.get_stats()