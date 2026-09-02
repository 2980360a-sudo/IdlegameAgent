# IdleAgent v0.6.0 - core/state.py
# 统一数据模型：所有引擎与适配器共享的 Pydantic 结构

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ActionType(str, Enum):
    """原子操作类型（与适配器 execute_action 解耦的契约）。"""
    CLICK = 'click'
    NAVIGATE = 'navigate'
    SELECT = 'select'
    WAIT = 'wait'
    SCROLL = 'scroll'
    INPUT = 'input'


class EventType(str, Enum):
    """游戏事件类型。"""
    DEATH = 'death'
    LOW_HP = 'low_hp'
    LEVEL_UP = 'level_up'
    POPUP = 'popup'
    COMPLETION = 'completion'
    ERROR = 'error'
    INFO = 'info'


class SkillInfo(BaseModel):
    name: str
    level: int
    xp: int = 0
    mastery_level: Optional[int] = None
    mastery_pool: Optional[int] = None


class ResourceInfo(BaseModel):
    name: str
    quantity: float = 0
    threshold: Optional[float] = None
    is_locked: bool = False


class EquipmentInfo(BaseModel):
    slot: str
    name: str
    tier: str = ''


class GameEvent(BaseModel):
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    severity: str = 'info'
    details: Dict[str, Any] = Field(default_factory=dict)


class Action(BaseModel):
    action_type: str
    target: str
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ''


class DOMMap(BaseModel):
    game_name: str
    selectors: Dict[str, str] = Field(default_factory=dict)


class GameState(BaseModel):
    game_name: str
    captured_at: datetime = Field(default_factory=datetime.now)
    gold: Optional[int] = None
    slayer_coins: Optional[int] = None
    bank_used: Optional[int] = None
    bank_max: Optional[int] = None
    skills: Dict[str, SkillInfo] = Field(default_factory=dict)
    resources: Dict[str, ResourceInfo] = Field(default_factory=dict)
    equipment: Dict[str, EquipmentInfo] = Field(default_factory=dict)
    active_action: Optional[str] = None
    active_skill: Optional[str] = None
    combat_active: bool = False
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    combat_level: Optional[int] = None
    food: Optional[Dict[str, Any]] = None
    auto_eat_tier: Optional[int] = None
    slayer_task: Optional[Dict[str, Any]] = None
    death_popup_visible: bool = False
    township: Optional[Dict[str, Any]] = None
    farming: Optional[Dict[str, Any]] = None
    astrology: Optional[Dict[str, Any]] = None
    bank_item_count: Optional[int] = None
    bank_locked_count: Optional[int] = None
    active_potions: List[Dict[str, Any]] = Field(default_factory=list)
    raw_probe: Optional[Dict[str, Any]] = None
    completion_percent: Optional[float] = None


class DiagnosisResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    game_name: str
    current_state: GameState
    bottlenecks: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class Plan(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    game_name: str
    short_term_goals: List[str] = Field(default_factory=list)
    mid_term_goals: List[str] = Field(default_factory=list)
    long_term_goals: List[str] = Field(default_factory=list)
    priority_queue: List[Dict[str, Any]] = Field(default_factory=list)


class Decision(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    game_name: str
    plan_id: Optional[str] = None
    actions: List[Action] = Field(default_factory=list)
    reason: str = ''
    confidence: float = 1.0


class ExecutionResult(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    game_name: str
    decision_id: Optional[str] = None
    success: bool = True
    actions_executed: int = 0
    errors: List[str] = Field(default_factory=list)
    state_after: Optional[GameState] = None
