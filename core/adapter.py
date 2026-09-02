# IdleAgent v0.4.0 - core/adapter.py
# GameAdapter 抽象基类：每个新游戏只需实现 4 个接口，核心引擎完全复用

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .state import GameState, GameEvent, Action, DOMMap


class GameAdapter(ABC):
    """通用挂机游戏适配器抽象基类。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config or {}
        self.name = self.config.get('name', 'Unknown Game')
        self.url = self.config.get('url', '')
        self.version = self.config.get('version', '1.0')

    # ---------- 4 个必须实现的接口 ----------

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
        """将游戏原始 DOM 映射为统一结构。"""
        pass

    @abstractmethod
    async def watch_events(self, page) -> List[GameEvent]:
        """监听游戏事件：升级、死亡、弹窗、完成度变化等。"""
        pass

    # ---------- 可选钩子（引擎会调用，子类可覆盖） ----------

    async def pre_boot(self, page) -> None:
        """浏览器启动前的准备钩子。"""
        pass

    async def post_shutdown(self, page) -> None:
        """关闭前的清理钩子。"""
        pass

    async def diagnose_custom(self, state: GameState) -> Dict[str, Any]:
        """游戏专用诊断：返回 {'warnings': [...], 'recommendations': [...]}。"""
        return {'warnings': [], 'recommendations': []}

    async def guards(self, page) -> Dict[str, Any]:
        """游戏专用守卫（药剂修正 / 动作恢复等），默认不执行。"""
        return {}

    # ---------- 规则读取 ----------

    def get_safety_rules(self) -> Dict[str, Any]:
        return self.config.get('safety', {})

    def get_priority_rules(self) -> Dict[str, Any]:
        return self.config.get('priorities', {})

    def get_resource_rules(self) -> Dict[str, Any]:
        return self.config.get('resources', {})

    # ---------- YAML 规则加载辅助 ----------

    @staticmethod
    def load_rules(game_id: str, base_dir: str = None) -> Dict[str, Any]:
        """加载并合并 `_base.yaml` 与 `<game_id>.yaml` 规则配置。

        规则文件查找顺序（相对项目根目录）:
            config/rules/<game_id>.yaml  (具体游戏，覆盖基础)
            config/rules/_base.yaml       (所有游戏共享)
        """
        import yaml

        if base_dir is None:
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config', 'rules',
            )

        merged: Dict[str, Any] = {}

        def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """递归合并字典，override 优先。"""
            result = dict(base)
            for k, v in (override or {}).items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = _merge(result[k], v)
                else:
                    result[k] = v
            return result

        base_path = os.path.join(base_dir, '_base.yaml')
        game_path = os.path.join(base_dir, f'{game_id}.yaml')

        for path in (base_path, game_path):
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        merged = _merge(merged, yaml.safe_load(f) or {})
                except Exception as e:  # 规则文件损坏不应阻止启动
                    print(f'[Adapter] 加载规则文件失败 {path}: {e}')

        return merged
