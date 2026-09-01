import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket

class ConnectionManager:
    """管理所有活跃的 WebSocket 连接，支持广播"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """向所有前端客户端推送消息"""
        if not self.active_connections:
            return
        # 如果某个连接断开，捕获异常并移除
        disconnected = []
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(conn)
        for conn in disconnected:
            self.disconnect(conn)

# 全局单例
manager = ConnectionManager()
