# IdleAgent v0.6.0 - core/storage.py
# SQLite 持久化：决策日志 + 状态快照 + 审计记录 + 游戏事件

import os
import json
import sqlite3
import threading
import time
from typing import List, Dict, Any, Optional


class Storage:
    """线程安全的 SQLite 持久化层。

    表结构:
        logs            — 决策日志（含诊断/规划/决策/执行/系统/事件）
        state_snapshots — 游戏状态快照（支持历史回溯）
        decisions       — 每次决策及其操作序列（审计）
        events          — 游戏事件（升级/死亡/弹窗等）
    """

    def __init__(self, db_path: str = None):
        db_path = db_path or os.environ.get(
            'STATE_DB', os.path.join('state', 'idleagent.db')
        )
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _ensure_column(self, table: str, column: str, decl: str):
        cols = [r['name'] for r in self._conn.execute(f'PRAGMA table_info({table})').fetchall()]
        if column not in cols:
            self._conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {decl}')

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data TEXT
                );
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    game_name TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    game_name TEXT NOT NULL,
                    reason TEXT,
                    confidence REAL,
                    actions TEXT,
                    state TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    user_id INTEGER,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'info',
                    details TEXT
                );
                """
            )
            # 旧库迁移：为 logs / decisions 补充 user_id 列
            self._ensure_column('logs', 'user_id', 'INTEGER')
            self._ensure_column('decisions', 'user_id', 'INTEGER')
            self._ensure_column('state_snapshots', 'user_id', 'INTEGER')
            self._conn.commit()

    # ---------- 日志 ----------

    def add_log(self, level: str, module: str, message: str,
                data: Optional[Dict] = None, user_id: Optional[int] = None):
        with self._lock:
            self._conn.execute(
                'INSERT INTO logs (timestamp, level, module, message, data, user_id) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (time.time(), level, module, message,
                 json.dumps(data or {}, ensure_ascii=False), user_id),
            )
            self._conn.commit()

    def get_logs(self, limit: int = 100, level: str = None, module: str = None,
                 user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            query = 'SELECT * FROM logs'
            conds, params = [], []
            if level:
                conds.append('level = ?')
                params.append(level)
            if module:
                conds.append('module = ?')
                params.append(module)
            if user_id is not None:
                conds.append('user_id = ?')
                params.append(user_id)
            if conds:
                query += ' WHERE ' + ' AND '.join(conds)
            query += ' ORDER BY id DESC LIMIT ?'
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()
            return [self._row_to_json(r) for r in rows]

    @staticmethod
    def _row_to_json(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for key in ('data', 'details', 'payload', 'actions', 'state'):
            if key in d:
                try:
                    d[key] = json.loads(d[key]) if d[key] else ([] if key == 'actions' else {})
                except json.JSONDecodeError:
                    d[key] = {} if key != 'actions' else []
        return d

    # ---------- 状态快照 ----------

    def save_state(self, state, user_id: Optional[int] = None) -> int:
        """保存 GameState 快照，返回自增 id。"""
        payload = json.dumps(state, ensure_ascii=False, default=str)
        with self._lock:
            cur = self._conn.execute(
                'INSERT INTO state_snapshots (timestamp, game_name, payload, user_id) '
                'VALUES (?, ?, ?, ?)',
                (time.time(), getattr(state, 'game_name', 'unknown'), payload, user_id),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_snapshots(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if user_id is not None:
                rows = self._conn.execute(
                    'SELECT * FROM state_snapshots WHERE user_id = ? ORDER BY id DESC LIMIT ?',
                    (user_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    'SELECT * FROM state_snapshots ORDER BY id DESC LIMIT ?', (limit,)
                ).fetchall()
            return [self._row_to_json(r) for r in rows]

    # ---------- 决策审计 ----------

    def save_decision(self, decision, state=None, user_id: Optional[int] = None):
        actions = [a.model_dump() if hasattr(a, 'model_dump') else a for a in decision.actions]
        state_json = json.dumps(
            state.model_dump() if hasattr(state, 'model_dump') else state,
            ensure_ascii=False, default=str,
        ) if state is not None else None
        with self._lock:
            self._conn.execute(
                'INSERT INTO decisions (timestamp, game_name, reason, confidence, actions, state, user_id) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (
                    time.time(), decision.game_name, decision.reason,
                    decision.confidence, json.dumps(actions, ensure_ascii=False, default=str),
                    state_json, user_id,
                ),
            )
            self._conn.commit()

    def get_decisions(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if user_id is not None:
                rows = self._conn.execute(
                    'SELECT * FROM decisions WHERE user_id = ? ORDER BY id DESC LIMIT ?',
                    (user_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    'SELECT * FROM decisions ORDER BY id DESC LIMIT ?', (limit,)
                ).fetchall()
            return [self._row_to_json(r) for r in rows]

    # ---------- 游戏事件 ----------

    def save_event(self, event_type: str, severity: str = 'info',
                   details: Optional[Dict] = None, user_id: Optional[int] = None):
        with self._lock:
            self._conn.execute(
                'INSERT INTO events (timestamp, user_id, event_type, severity, details) '
                'VALUES (?, ?, ?, ?, ?)',
                (time.time(), user_id, event_type, severity,
                 json.dumps(details or {}, ensure_ascii=False)),
            )
            self._conn.commit()

    def get_events(self, limit: int = 100, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if user_id is not None:
                rows = self._conn.execute(
                    'SELECT * FROM events WHERE user_id = ? ORDER BY id DESC LIMIT ?',
                    (user_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    'SELECT * FROM events ORDER BY id DESC LIMIT ?', (limit,)
                ).fetchall()
            return [self._row_to_json(r) for r in rows]

    def save_diagnosis(self, diagnosis, user_id: Optional[int] = None):
        self.add_log(
            'info', 'diagnosis',
            f'诊断: 警告 {len(diagnosis.warnings)} 条, 建议 {len(diagnosis.recommendations)} 条',
            {'recommendations': diagnosis.recommendations, 'warnings': diagnosis.warnings},
            user_id=user_id,
        )

    def save_execution(self, result, user_id: Optional[int] = None):
        self.add_log(
            'info' if result.success else 'error', 'execution',
            f'执行 {result.actions_executed} 个操作, 成功={result.success}',
            {'errors': result.errors},
            user_id=user_id,
        )

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
