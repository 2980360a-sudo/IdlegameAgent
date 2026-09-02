from fastapi import APIRouter, Depends
from api.dependencies import get_runtime

router = APIRouter()


@router.get("/status")
async def get_status(runtime=Depends(get_runtime)):
    return await runtime.get_status()
