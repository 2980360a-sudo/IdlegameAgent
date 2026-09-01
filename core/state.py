# IdleAgent v0.2.0 - core/state.py
# Generated: 2026-09-01

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SkillInfo(BaseModel):
    name: str
    level: int
    xp: int
    mastery_level: Optional[int] = None
    mastery_pool: Optional[int] = None


class ResourceInfo(BaseModel):
    name: str
    quantity: int
    threshold: Optional[int] = None
    is_locked: bool = False


class EquipmentInfo(BaseModel):
    slot: str
    name: str
    tier: str


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
    township: Optional[Dict[str, Any]] = None
    farming: Optional[Dict[str, Any]] = None
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
