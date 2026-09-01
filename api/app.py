from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from datetime import datetime

# 导入你的路由和 manager（确保这些文件存在）
from api.routes import status, rules, logs, control
from api.managers import manager

app = FastAPI(title="IdleAgent API", version="0.2.1")

# 允许跨域（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 1. 先注册 REST 路由 =====
app.include_router(status.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(control.router, prefix="/api")

# ===== 2. 再注册 WebSocket 路由（必须在静态文件挂载之前） =====
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ===== 3. 最后挂载静态文件（放在最后，让它作为兜底） =====
# 使用绝对路径，确保指向你的 dashboard 文件夹
dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
# 如果上面的相对路径不对，请改为绝对路径，例如：
# dashboard_path = r"D:\本地项目目录\IdlegameAgent-main\dashboard"
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
else:
    print(f"警告：dashboard 目录不存在于 {dashboard_path}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
