# IdleAgent v0.6.0 - core/melvor_agent.py
# Melvor 挂机 Agent 会话管理：账号存储 + 三种运行模式 + 事件/决策追踪

import os
import json
import time
import asyncio
import sqlite3
import threading
from enum import Enum
from typing import Dict, Any, List, Optional

from core.storage import Storage
from core.llm import LLMClient
from core.state import GameState, Action, ActionType, GameEvent, SkillInfo, ResourceInfo


class RunMode(str, Enum):
    EFFICIENCY = 'efficiency'   # 最高效率：LLM 全权，允许角色死亡
    SURVIVAL = 'survival'       # 极限模式：LLM 全权，但 100% 不允许死亡
    MANUAL = 'manual'           # 用户脚本：不参与 LLM 决策


RUN_MODE_LABELS = {
    RunMode.EFFICIENCY.value: '最高效率',
    RunMode.SURVIVAL.value: '极限不死亡',
    RunMode.MANUAL.value: '用户脚本',
}

RUN_MODE_DESC = {
    RunMode.EFFICIENCY.value: '完全放开操作权限给 LLM，自动执行最高效率的挂机动作（角色可能死亡）',
    RunMode.SURVIVAL.value: '完全放开操作权限给 LLM，但 100% 不允许角色死亡',
    RunMode.MANUAL.value: '执行用户自己配置的脚本，LLM 不参与决策',
}


# ------------------------------------------------------------
# Melvor 账号存储（每用户一套 Melvor 云账号/角色/模式配置）
# ------------------------------------------------------------
class MelvorAccountStore:
    """持久化每个网站用户绑定的 Melvor 云账号与运行配置。"""

    def __init__(self, db_path: str = None):
        db_path = db_path or os.environ.get(
            'MELVOR_DB', os.path.join('state', 'melvor_accounts.db')
        )
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS melvor_accounts (
                    user_id INTEGER PRIMARY KEY,
                    account TEXT,
                    password TEXT,
                    character_index INTEGER,
                    mode TEXT,
                    script TEXT,
                    updated_at REAL
                )
                """
            )
            self._conn.commit()

    def save(self, user_id: int, account: str = None, password: str = None,
             character_index: int = None, mode: str = None, script: List = None):
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM melvor_accounts WHERE user_id = ?', (user_id,)
            ).fetchone()
            if row is None:
                self._conn.execute(
                    'INSERT INTO melvor_accounts (user_id, account, password, character_index, mode, script, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (user_id, account, password, character_index, mode,
                     json.dumps(script, ensure_ascii=False) if script is not None else None,
                     time.time()),
                )
            else:
                self._conn.execute(
                    'UPDATE melvor_accounts SET account=?, password=?, character_index=?, mode=?, script=?, updated_at=? '
                    'WHERE user_id=?',
                    (
                        account if account is not None else row['account'],
                        password if password is not None else row['password'],
                        character_index if character_index is not None else row['character_index'],
                        mode if mode is not None else row['mode'],
                        json.dumps(script, ensure_ascii=False) if script is not None else row['script'],
                        time.time(), user_id,
                    ),
                )
            self._conn.commit()

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM melvor_accounts WHERE user_id = ?', (user_id,)
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            try:
                d['script'] = json.loads(d['script']) if d.get('script') else []
            except json.JSONDecodeError:
                d['script'] = []
            return d

    def get_public(self, user_id: int) -> Optional[Dict[str, Any]]:
        """返回脱敏配置（不含密码）。"""
        d = self.get(user_id)
        if d is None:
            return None
        d.pop('password', None)
        return d

    def delete(self, user_id: int):
        with self._lock:
            self._conn.execute('DELETE FROM melvor_accounts WHERE user_id = ?', (user_id,))
            self._conn.commit()


# ------------------------------------------------------------
# Melvor Agent 会话
# ------------------------------------------------------------
class MelvorAgentSession:
    """单个用户的一个 Melvor 挂机会话。

    生命周期: idle -> connected(已登录+选角色) -> running(循环中) -> connected/stopped
    三种模式: efficiency / survival / manual
    """

    def __init__(self, user_id: int, adapter=None, llm: LLMClient = None,
                 storage: Storage = None, mock: bool = False):
        self.user_id = user_id
        self.adapter = adapter
        self.llm = llm
        self.storage = storage or Storage()
        self.mock = mock

        self.session_state = 'idle'  # idle | connected | running | error
        self.mode: Optional[str] = None
        self.character_index: Optional[int] = None
        self.character_label: Optional[str] = None

        self._page = None
        self._loop_task = None
        self._events: List[Dict[str, Any]] = []
        self._decisions: List[Dict[str, Any]] = []
        self._script: List[Dict[str, Any]] = []
        self._script_last_run: Dict[int, float] = {}

        # mock 专用状态
        self._mock_state = self._make_mock_state()
        self._mock_characters = [
            {'index': 0, 'label': '最后保存：2026/9/1 10:00:00'},
            {'index': 1, 'label': '最后保存：2026/8/28 22:30:00'},
        ]

    # ---------- 事件与决策追踪 ----------
    def _log_event(self, event_type: str, severity: str = 'info', details: Dict = None):
        ev = {
            'timestamp': time.time(), 'event_type': event_type,
            'severity': severity, 'details': details or {},
        }
        self._events.append(ev)
        if len(self._events) > 500:
            self._events = self._events[-300:]
        try:
            self.storage.save_event(event_type, severity, details, user_id=self.user_id)
        except Exception:
            pass

    def _log_decision(self, actions: List[Action], mode: str, reason: str = ''):
        dec = {
            'timestamp': time.time(), 'mode': mode, 'reason': reason,
            'actions': [a.model_dump() for a in actions],
        }
        self._decisions.append(dec)
        if len(self._decisions) > 500:
            self._decisions = self._decisions[-300:]
        try:
            self.storage.add_log('decision', 'decision',
                                 f'{RUN_MODE_LABELS.get(mode, mode)} 决策 {len(actions)} 个动作',
                                 {'actions': dec['actions']}, user_id=self.user_id)
        except Exception:
            pass

    def get_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._events[-limit:]))

    def get_decisions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._decisions[-limit:]))

    # ---------- 登录 / 角色 ----------
    async def login(self, account: str, password: str) -> Dict[str, Any]:
        self._log_event('login', 'info', {'account': account})
        if self.mock:
            self.session_state = 'connected'
            await asyncio.sleep(0.2)
            return {'ok': True, 'characters': self._mock_characters}

        try:
            self._page = await self.adapter.login_cloud(account, password)
            self.session_state = 'connected'
            return {'ok': True, 'characters': await self.list_characters()}
        except Exception as e:
            self.session_state = 'error'
            self._log_event('login_error', 'error', {'error': str(e)})
            return {'ok': False, 'error': str(e)}

    async def list_characters(self) -> List[Dict[str, Any]]:
        if self.mock:
            return self._mock_characters
        try:
            return await self.adapter.list_characters(self._page)
        except Exception as e:
            self._log_event('list_characters_error', 'error', {'error': str(e)})
            return []

    async def select_character(self, index: int) -> Dict[str, Any]:
        if self.mock:
            self.character_index = index
            self.character_label = self._mock_characters[index]['label'] if index < len(self._mock_characters) else ''
            self._log_event('character_selected', 'info', {'index': index, 'label': self.character_label})
            return {'ok': True, 'index': index, 'label': self.character_label}

        try:
            ok = await self.adapter.select_character(self._page, index)
            if ok:
                self.character_index = index
                self._log_event('character_selected', 'info', {'index': index})
                return {'ok': True, 'index': index}
            return {'ok': False, 'error': '选择角色失败'}
        except Exception as e:
            self._log_event('select_error', 'error', {'error': str(e)})
            return {'ok': False, 'error': str(e)}

    # ---------- 启停 ----------
    async def start(self, mode: str, script: List[Dict] = None) -> Dict[str, Any]:
        if mode not in RUN_MODE_LABELS:
            return {'ok': False, 'error': f'未知模式: {mode}'}
        self.mode = mode
        if script is not None:
            self._script = script
            self._script_last_run = {}
        self.session_state = 'running'
        self._log_event('start', 'info', {'mode': mode, 'label': RUN_MODE_LABELS[mode]})
        self._loop_task = asyncio.create_task(self._loop())
        return {'ok': True, 'mode': mode}

    async def stop(self) -> Dict[str, Any]:
        if self._loop_task is not None:
            self._loop_task.cancel()
            self._loop_task = None
        if self.session_state != 'idle':
            self.session_state = 'connected'
        self._log_event('stop', 'info', {})
        return {'ok': True}

    async def disconnect(self):
        """停止并关闭浏览器（完全退出）。"""
        await self.stop()
        if self.mock:
            self.session_state = 'idle'
            return
        try:
            if self.adapter is not None:
                await self.adapter.browser.close()
        except Exception:
            pass
        self._page = None
        self.session_state = 'idle'

    # ---------- 状态读取 ----------
    async def get_status(self) -> Dict[str, Any]:
        state = await self._read_state()
        return {
            'session_state': self.session_state,
            'mode': self.mode,
            'mode_label': RUN_MODE_LABELS.get(self.mode, '') if self.mode else '',
            'character_index': self.character_index,
            'character_label': self.character_label,
            'game': state.model_dump() if state else None,
            'script': self._script,
        }

    async def _read_state(self) -> Optional[GameState]:
        if self.mock:
            return self._mock_evolve_state()
        if self._page is None:
            return None
        try:
            return await self.adapter.read_state(self._page)
        except Exception as e:
            self._log_event('read_state_error', 'error', {'error': str(e)})
            return None

    async def _watch_events(self) -> List[GameEvent]:
        if self.mock:
            return []
        try:
            return await self.adapter.watch_events(self._page)
        except Exception:
            return []

    # ---------- 主循环 ----------
    async def _loop(self):
        interval = float(os.environ.get('MELVOR_LOOP_INTERVAL', '10'))
        while self.session_state == 'running':
            try:
                state = await self._read_state()
                if state is not None:
                    self.storage.save_state(state, user_id=self.user_id)
                    for ev in await self._watch_events():
                        self._log_event(ev.event_type, ev.severity, ev.details)

                actions = await self._decide(state)
                for action in actions:
                    ok = await self._execute(action)
                    self._log_event(
                        'action', 'info',
                        {'action_type': action.action_type, 'target': action.target, 'ok': ok},
                    )
                self._log_decision(actions, self.mode or '', reason=self._last_reason)
                self._last_reason = ''
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log_event('loop_error', 'error', {'error': str(e)})
            await asyncio.sleep(interval)

    async def _execute(self, action: Action) -> bool:
        if self.mock:
            await asyncio.sleep(0.05)
            return True
        if self._page is None:
            return False
        try:
            if action.action_type == 'operation':
                return await self.adapter.execute_operation(self._page, action.target)
            return await self.adapter.execute_action(self._page, action)
        except Exception:
            return False

    # ---------- 三种模式决策 ----------
    async def _decide(self, state: GameState) -> List[Action]:
        if state is None:
            return []
        if self.mode == RunMode.MANUAL.value:
            return self._manual_actions()
        if self.mode == RunMode.EFFICIENCY.value:
            return await self._decide_efficiency(state)
        if self.mode == RunMode.SURVIVAL.value:
            return await self._decide_survival(state)
        return []

    async def _decide_efficiency(self, state: GameState) -> List[Action]:
        """最高效率：LLM 全权，允许死亡。"""
        actions = await self._llm_actions(state, RunMode.EFFICIENCY.value)
        if actions:
            self._last_reason = 'LLM 最高效率决策'
            return actions
        # 无 LLM 时维持现状
        self._last_reason = '无 LLM，维持现状'
        return [Action(action_type=ActionType.WAIT.value, target='body',
                       params={'duration': 5}, reason='最高效率模式，维持现状')]

    async def _decide_survival(self, state: GameState) -> List[Action]:
        """极限模式：LLM 全权，但 100% 不死亡。"""
        # 1. 硬安全保护优先
        guard = self._survival_guard(state)
        if guard:
            self._last_reason = '生存保护触发'
            return guard
        # 2. LLM 决策 + 风险过滤
        actions = await self._llm_actions(state, RunMode.SURVIVAL.value)
        filtered = self._filter_death_risky(actions)
        self._last_reason = f'LLM 极限决策（过滤 {len(actions) - len(filtered)} 个风险动作）'
        return filtered

    def _manual_actions(self) -> List[Action]:
        """用户脚本：按 cooldown 轮询执行，LLM 不参与。"""
        now = time.time()
        due = []
        for i, step in enumerate(self._script):
            try:
                interval = float(step.get('interval', 0) or 0)
            except (TypeError, ValueError):
                interval = 0
            if i in self._script_last_run and now - self._script_last_run[i] < interval:
                continue
            due.append(Action(
                action_type=str(step.get('action_type', 'wait')),
                target=str(step.get('target', '')),
                params=step.get('params', {}) or {},
                reason=str(step.get('reason', '用户脚本')),
            ))
            self._script_last_run[i] = now
        self._last_reason = f'用户脚本执行 {len(due)} 个动作'
        return due

    # ---------- LLM 决策 ----------
    async def _llm_actions(self, state: GameState, mode: str) -> List[Action]:
        if self.llm is None or not self.llm.configured:
            return []
        prompt = self._build_llm_prompt(state, mode)
        try:
            raw = await self.llm.chat([
                {'role': 'system', 'content': '你是 Melvor Idle 挂机自动化决策助手，只输出 JSON。'},
                {'role': 'user', 'content': prompt},
            ])
            return self._parse_actions(raw)
        except Exception as e:
            self._log_event('llm_error', 'warning', {'error': str(e)})
            return []

    def _build_llm_prompt(self, state: GameState, mode: str) -> str:
        skills = ', '.join(
            f'{k}=Lv{v.level}' for k, v in list(state.skills.items())[:25]
        ) or '无'
        hp = state.hp or 0
        max_hp = state.max_hp or 1
        mode_guide = {
            RunMode.EFFICIENCY.value: '追求最高效率/进度，忽略死亡风险，可以挑战高收益但危险的战斗',
            RunMode.SURVIVAL.value: '追求效率但绝对不允许角色死亡，避免任何可能导致死亡的操作',
        }.get(mode, '')
        return (
            '请根据当前游戏状态给出下一步操作（只输出 JSON）。\n'
            f'运行模式要求: {mode_guide}\n'
            f'金币: {state.gold or 0}, 仓库: {state.bank_used or 0}/{state.bank_max or 0}\n'
            f'HP: {hp}/{max_hp}, 战斗中: {"是" if state.combat_active else "否"}\n'
            f'当前动作: {state.active_action or "无"}\n'
            f'技能等级: {skills}\n'
            '严格输出 JSON: {"actions": [{"action_type": "click|navigate|wait", '
            '"target": "目标", "reason": "理由"}]}'
        )

    def _parse_actions(self, raw: str) -> List[Action]:
        import re
        text = (raw or '').strip()
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.IGNORECASE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if not m:
                return []
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []
        actions = []
        for item in data.get('actions', []):
            try:
                actions.append(Action(
                    action_type=str(item.get('action_type', 'wait')),
                    target=str(item.get('target', '')),
                    params=item.get('params', {}) or {},
                    reason=str(item.get('reason', 'LLM 决策')),
                ))
            except Exception:
                continue
        return actions

    # ---------- 生存保护 ----------
    def _survival_guard(self, state: GameState) -> List[Action]:
        """返回紧急安全动作（非空表示必须优先执行，阻断其它决策）。"""
        if state.death_popup_visible:
            return [Action(action_type=ActionType.WAIT.value, target='body',
                           params={'duration': 120}, reason='检测到死亡弹窗，暂停操作')]
        if state.hp and state.max_hp and state.max_hp > 0:
            ratio = state.hp / state.max_hp
            if state.combat_active and ratio < 0.3:
                return [Action(action_type=ActionType.NAVIGATE.value, target='非战斗技能页',
                               reason=f'HP 过低({ratio:.0%})，强制脱离战斗')]
        return []

    _RISKY_TOKENS = ('combat', '战斗', 'dungeon', '地下城', 'attack', '攻击', 'fight', '怪物', 'enemy')

    def _filter_death_risky(self, actions: List[Action]) -> List[Action]:
        safe = []
        for a in actions:
            if self._is_death_risky(a):
                self._log_event('blocked', 'warning',
                                {'action_type': a.action_type, 'target': a.target,
                                 'reason': 'survival 模式拦截死亡风险动作'})
                continue
            safe.append(a)
        return safe

    def _is_death_risky(self, action: Action) -> bool:
        target = (action.target or '').lower()
        if action.action_type == ActionType.NAVIGATE.value:
            return any(t in target for t in ('combat', '战斗', 'dungeon', '地下城', 'monster', '怪物'))
        if action.action_type == ActionType.CLICK.value:
            return any(t in target for t in ('attack', '攻击', 'fight', '战斗', 'enemy', '怪物'))
        return False

    # ---------- Mock 状态 ----------
    def _make_mock_state(self) -> GameState:
        skills = {
            'woodcutting': SkillInfo(name='woodcutting', level=99, xp=13034431),
            'fishing': SkillInfo(name='fishing', level=87, xp=4022331),
            'mining': SkillInfo(name='mining', level=92, xp=6500000),
            'astrology': SkillInfo(name='astrology', level=120, xp=104273167),
        }
        return GameState(
            game_name='Melvor Idle', gold=12345678, slayer_coins=987654,
            bank_used=320, bank_max=500, skills=skills,
            resources={'gold': ResourceInfo(name='gold', quantity=12345678)},
            active_action='Astrology', active_skill='astrology',
            combat_active=False, hp=100, max_hp=100,
            active_potions=[{'action': 'melvorD:Astrology', 'item': 'Secret_Stardust_Potion_III', 'charges': 12}],
        )

    def _mock_evolve_state(self) -> GameState:
        s = self._mock_state
        s.gold = (s.gold or 0) + 137
        if s.bank_used is not None:
            s.bank_used = min(s.bank_max or 1, s.bank_used + 1)
        # 模拟战斗模式下的 HP 波动（用于展示）
        if self.mode == RunMode.SURVIVAL.value:
            s.combat_active = True
            s.hp = max(1, (s.hp or 100) - 3)
            if (s.hp or 0) <= 5:
                s.hp = 100
        return s
