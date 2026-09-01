"""
API 依赖注入模块
提供全局 AgentRuntime 实例，供路由层调用
支持模拟数据运行，并可无缝切换到真实游戏适配器
"""

import time
import asyncio
from typing import Dict, Any, List, Optional

# 未来接入真实适配器时取消注释
# from adapters.melvor_idle import MelvorIdleAdapter
# from core.browser import BrowserManager


class AgentRuntime:
    """
    Agent 运行时上下文
    管理状态、日志、运行标志，并负责生成模拟数据（或真实数据）
    """

    def __init__(self):
        self.is_running = False
        self.logs: List[Dict[str, Any]] = []
        self._counter = 0
        self._mock_resources = {"gold": 1234.5, "wood": 567, "stone": 890}
        self._mock_combat = {"hp": 850, "max_hp": 1000, "in_combat": False}

        # 扩展点：真实适配器与浏览器管理器（暂未初始化）
        # self.adapter = None
        # self.browser_manager = None

    # ============================================================
    # 状态获取（当前返回模拟数据，可切换为真实数据）
    # ============================================================
    def get_status(self) -> Dict[str, Any]:
        """
        返回当前游戏状态（模拟数据）
        未来可改为调用适配器的 read_state() 获取真实数据
        """
        # 模拟数据缓慢增长，让仪表盘有动态效果
        self._mock_resources["gold"] += 0.5
        self._mock_resources["wood"] += 0.3
        self._mock_resources["stone"] += 0.2

        return {
            "resources": self._mock_resources.copy(),
            "combat": self._mock_combat.copy(),
            "is_running": self.is_running,
            "timestamp": time.time()
        }

    # 可选：异步获取真实状态（需接入浏览器和适配器）
    # async def fetch_real_status(self) -> Dict[str, Any]:
    #     if not self.adapter or not self.browser_manager:
    #         return self.get_status()
    #     try:
    #         page = self.browser_manager.get_page()
    #         state = await self.adapter.read_state(page)
    #         return state.dict()
    #     except Exception as e:
    #         print(f"读取真实状态失败: {e}")
    #         return self.get_status()

    # ============================================================
    # 日志管理
    # ============================================================
    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """返回最近的日志，按时间倒序（最新在前）"""
        # 如果日志为空，生成一些示例日志
        if not self.logs:
            self._generate_sample_logs()
        return self.logs[-limit:]

    def add_log(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        """添加一条日志"""
        self.logs.append({
            "id": self._counter,
            "timestamp": time.time(),
            "level": level,       # info, warning, error, action
            "module": module,     # diagnosis, planning, decision, execution, system
            "message": message,
            "data": data or {}
        })
        self._counter += 1
        # 限制日志长度，防止内存溢出
        if len(self.logs) > 1000:
            self.logs = self.logs[-500:]

    def _generate_sample_logs(self):
        """生成示例日志，让前端有数据显示"""
        sample = [
            ("info", "system", "Agent 启动完成，等待指令"),
            ("info", "diagnosis", "诊断完成：当前资源充足，建议升级伐木"),
            ("decision", "decision", "决策：执行伐木操作"),
            ("action", "execution", "执行动作：click #woodcutting"),
            ("info", "system", "定时循环开始，间隔 5 秒"),
            ("warning", "monitor", "仓库木材接近上限，建议出售"),
            ("info", "execution", "动作执行成功，木材 +10"),
        ]
        for level, module, msg in sample:
            self.add_log(level, module, msg)

    # ============================================================
    # 控制方法（由 control 路由调用）
    # ============================================================
    def start(self):
        """启动 Agent（设置运行标志，并添加启动日志）"""
        if self.is_running:
            return
        self.is_running = True
        self.add_log("info", "system", "Agent 已启动（模拟模式）")

    def stop(self):
        """停止 Agent"""
        if not self.is_running:
            return
        self.is_running = False
        self.add_log("info", "system", "Agent 已停止")

    def pause(self):
        """暂停 Agent（与停止相同，但语义区分）"""
        if not self.is_running:
            return
        self.is_running = False
        self.add_log("warning", "system", "Agent 已暂停")

    # 扩展：真实启动/停止可在此处调用浏览器和适配器
    # async def start_real(self):
    #     if not self.browser_manager:
    #         self.browser_manager = BrowserManager()
    #         await self.browser_manager.start()
    #     # 登录、加载存档等
    #     self.is_running = True


# ============================================================
# 全局单例实例
# ============================================================
_runtime = AgentRuntime()

def get_runtime() -> AgentRuntime:
    """FastAPI 依赖项，返回全局 AgentRuntime 实例"""
    return _runtime
