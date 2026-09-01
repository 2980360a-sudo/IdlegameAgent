import time
from typing import Dict, Any, List, Optional

class AgentRuntime:
    def __init__(self):
        self.is_running = False
        self.logs: List[Dict[str, Any]] = []
        self._counter = 0
        self._mock_resources = {"gold": 1234.5, "wood": 567, "stone": 890}
        self._mock_combat = {"hp": 850, "max_hp": 1000, "in_combat": False}

    def get_status(self) -> Dict[str, Any]:
        # 模拟数字缓慢增长
        self._mock_resources["gold"] += 0.5
        self._mock_resources["wood"] += 0.3
        self._mock_resources["stone"] += 0.2
        return {
            "resources": self._mock_resources.copy(),
            "combat": self._mock_combat.copy(),
            "is_running": self.is_running,
            "timestamp": time.time()
        }

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.logs[-limit:]

    def add_log(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        self.logs.append({
            "id": self._counter,
            "timestamp": time.time(),
            "level": level,
            "module": module,
            "message": message,
            "data": data or {}
        })
        self._counter += 1
        if len(self.logs) > 1000:
            self.logs = self.logs[-500:]

_runtime = AgentRuntime()

def get_runtime() -> AgentRuntime:
    return _runtime
