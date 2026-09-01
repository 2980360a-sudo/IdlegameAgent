from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from datetime import datetime

from api.managers import manager
from api.routes import status, rules, logs, control

# 实例化 FastAPI
app = FastAPI(title="IdleAgent API", version="0.2.1")

# 允许跨域（开发环境方便）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. 挂载 REST 路由
app.include_router(status.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(control.router, prefix="/api")

# 2. 挂载前端静态文件（让 FastAPI 直接托管 dashboard）
# 假设 dashboard 目录在项目根目录下
dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")

# 3. WebSocket 端点
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # 保持长连接，接收前端发来的 ping（可选）
        while True:
            data = await websocket.receive_text()
            # 可以在这里处理前端发来的指令，比如 "refresh_status"
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 4. 健康检查
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# 注：依赖项和全局 Agent 实例将在下一步注入
