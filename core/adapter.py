# IdleAgent v0.2.0 - core/adapter.py
# Generated: 2026-09-01

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .state import GameState, GameEvent, Action, DOMMap


class GameAdapter(ABC):
    """通用挂机游戏适配器抽象基类。
    每个新游戏只需实现这4个接口，核心引擎完全复用。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', 'Unknown Game')
        self.url = config.get('url', '')
        self.version = config.get('version', '1.0')

    @abstractmethod
    async def read_state(self, page) -> GameState:
        """从游戏页面提取统一状态。"""
        pass

    @abstractmethod
    async def execute_action(self, page, action: Action) -> bool:
        """执行原子操作：点击、选择、输入、等待、导航等。"""
        pass

    @abstractmethod
    def map_dom(self, raw_html: str) -> DOMMap:
        """将游戏原始DOM映射为统一结构。"""
        pass

    @abstractmethod
    async def watch_events(self, page) -> List[GameEvent]:
        """监听游戏事件：升级、死亡、弹窗、完成度变化等。"""
        pass

    # 可选钩子
    async def pre_boot(self, page) -> None:
        pass

    async def post_shutdown(self, page) -> None:
        pass

    def get_safety_rules(self) -> Dict[str, Any]:
        return self.config.get('safety', {})

    def get_priority_rules(self) -> Dict[str, Any]:
        return self.config.get('priorities', {})

    def get_resource_rules(self) -> Dict[str, Any]:
        return self.config.get('resources', {})
