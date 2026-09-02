from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.dependencies import get_runtime, AgentRuntime

router = APIRouter()


class ControlResponse(BaseModel):
    status: str
    message: str


@router.post("/control/{action}", response_model=ControlResponse)
async def control_agent(action: str, runtime: AgentRuntime = Depends(get_runtime)):
    if action == "start":
        result = await runtime.start()
        return ControlResponse(
            status=result,
            message={
                'started': 'Agent 启动成功',
                'already': 'Agent 已在运行',
                'failed': 'Agent 启动失败（详见日志）',
            }.get(result, 'Agent 启动'),
        )

    elif action == "stop":
        result = await runtime.stop()
        return ControlResponse(
            status=result,
            message='Agent 已停止' if result == 'stopped' else 'Agent 未在运行',
        )

    elif action == "pause":
        result = await runtime.pause()
        return ControlResponse(status=result, message='Agent 已暂停')

    else:
        raise HTTPException(status_code=404, detail="Invalid action")
