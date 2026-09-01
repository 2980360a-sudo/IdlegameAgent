from typing import Optional, List, Dict, Any
from core.state import GameState, Action, GameEvent
from core.engine import DiagnosisEngine, PlanningEngine, DecisionEngine, ExecutionEngine
import time
import random

class AgentRuntime:
    """模拟 Agent 运行时，后续替换为真实的 Engine 调用"""
    def __init__(self):
        self.is_running = False
        self.current_state: Optional[GameState] = None
        self.logs: List[Dict[str, Any]] = []
        self._counter = 0

    def get_status(self) -> Dict[str, Any]:
        """返回当前状态（用于 /api/status）"""
        if not self.current_state:
            # 生成一个模拟状态
            self.current_state = GameState(
                resources={"gold": 1234.5, "wood": 567, "stone": 890},
                combat={"hp": 850, "max_hp": 1000, "in_combat": False},
                timestamp=time.time()
            )
        return self.current_state.dict()

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.logs[-limit:]

    def add_log(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        self.logs.append({
            "id": self._counter,
            "timestamp": time.time(),
            "level": level,  # info, warning, error, action
            "module": module,  # diagnosis, planning, decision, execution
            "message": message,
            "data": data or {}
        })
        self._counter += 1
        # 限制日志长度，防止内存溢出
        if len(self.logs) > 1000:
            self.logs = self.logs[-500:]

    async def run_cycle(self):
        """模拟一次完整的引擎循环（诊断->规划->决策->执行）"""
        if not self.is_running:
            return

        # 1. 诊断
        self.add_log("info", "diagnosis", "开始诊断游戏状态...")
        # TODO: 调用 DiagnosisEngine.diagnose()
        diagnosis_result = {"health": "ok", "bottleneck": "wood"}
        self.add_log("info", "diagnosis", f"诊断完成: 瓶颈={diagnosis_result['bottleneck']}", diagnosis_result)

        # 2. 规划
        self.add_log("info", "planning", "根据诊断结果生成计划...")
        plan = ["收集木头", "升级伐木场"]
        self.add_log("info", "planning", f"规划完成: {plan}", {"plan": plan})

        # 3. 决策
        self.add_log("info", "decision", "从计划中选择最优动作...")
        action = {"type": "click", "target": "wood_cutting", "reason": "wood is bottleneck"}
        self.add_log("info", "decision", f"决策: 执行 {action['target']}", action)

        # 4. 执行
        self.add_log("info", "execution", f"执行动作: {action['type']}->{action['target']}")
        # 模拟状态变化
        if self.current_state:
            self.current_state.resources["wood"] += 10
        self.add_log("action", "execution", f"成功执行 {action['target']}，木头 +10", {"new_wood": self.current_state.resources["wood"] if self.current_state else 0})

        # 广播更新（由外部调度器调用广播函数，这里只负责生成日志）

# 全局单例运行时
_runtime = AgentRuntime()

def get_runtime() -> AgentRuntime:
    return _runtime
