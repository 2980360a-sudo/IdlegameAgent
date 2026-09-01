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
        if runtime.is_running:
            return ControlResponse(status="already", message="Agent is already running.")
        runtime.is_running = True
        runtime.add_log("info", "system", "Agent started by user.")
        # 这里可以启动后台任务（APScheduler），但在当前简化版中，我们会让前端轮询 /status
        return ControlResponse(status="started", message="Agent started successfully.")
    
    elif action == "stop":
        if not runtime.is_running:
            return ControlResponse(status="already", message="Agent is already stopped.")
        runtime.is_running = False
        runtime.add_log("info", "system", "Agent stopped by user.")
        return ControlResponse(status="stopped", message="Agent stopped successfully.")
    
    elif action == "pause":
        runtime.is_running = False  # 模拟暂停
        runtime.add_log("warning", "system", "Agent paused by user.")
        return ControlResponse(status="paused", message="Agent paused.")
    
    else:
        raise HTTPException(status_code=404, detail="Invalid action")
