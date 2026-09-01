from fastapi import APIRouter, Depends, Query
from api.dependencies import get_runtime

router = APIRouter()

@router.get("/logs")
async def get_logs(limit: int = Query(50, ge=1, le=200), runtime=Depends(get_runtime)):
    logs = runtime.get_logs(limit)
    return {"total": len(logs), "logs": logs}
