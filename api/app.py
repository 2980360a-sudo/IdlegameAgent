from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from datetime import datetime

# 加载 .env（uvicorn 直接启动时也生效），必须在路由导入之前
load_dotenv()

from api.routes import status, rules, logs, control, auth, melvor
from api.managers import manager

app = FastAPI(title="IdleAgent API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. REST 路由（必须注册在静态文件挂载之前）
app.include_router(auth.router, prefix="/api")
app.include_router(melvor.router, prefix="/api")
app.include_router(status.router, prefix="/api")
app.include_router(rules.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(control.router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.6.0", "timestamp": datetime.now().isoformat()}


# 2. WebSocket 路由（必须在静态文件挂载之前）
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


# 3. 静态文件（dashboard 前端，放在最后作为兜底）
dashboard_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard")
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
else:
    print(f"警告：dashboard 目录不存在于 {dashboard_path}")
