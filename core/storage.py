# IdleAgent v0.5.0 - core/storage.py
# SQLite 持久化：决策日志 + 状态快照 + 审计记录

import os
import json
import sqlite3
import threading
import time
from typing import List, Dict, Any, Optional


class Storage:
    """线程安全的 SQLite 持久化层。

    表结构:
        logs            — 决策日志（含诊断/规划/决策/执行/系统）
        state_snapshots — 游戏状态快照（支持历史回溯）
        decisions       — 每次决策及其操作序列（审计）
    """

    def __init__(self, db_path: str = None):
        db_path = db_path or os.environ.get(
            'STATE_DB', os.path.join('state', 'idleagent.db')
        )
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
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
                """
            )
            self._conn.commit()

    # ---------- 日志 ----------

    def add_log(self, level: str, module: str, message: str, data: Optional[Dict] = None):
        with self._lock:
            self._conn.execute(
                'INSERT INTO logs (timestamp, level, module, message, data) '
                'VALUES (?, ?, ?, ?, ?)',
                (time.time(), level, module, message, json.dumps(data or {}, ensure_ascii=False)),
            )
            self._conn.commit()

    def get_logs(self, limit: int = 100, level: str = None, module: str = None) -> List[Dict[str, Any]]:
        with self._lock:
            query = 'SELECT * FROM logs'
            conds, params = [], []
            if level:
                conds.append('level = ?')
                params.append(level)
            if module:
                conds.append('module = ?')
                params.append(module)
            if conds:
                query += ' WHERE ' + ' AND '.join(conds)
            query += ' ORDER BY id DESC LIMIT ?'
            params.append(limit)
            rows = self._conn.execute(query, params).fetchall()
            return [self._row_to_log(r) for r in rows]

    @staticmethod
    def _row_to_log(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        try:
            d['data'] = json.loads(d.get('data') or '{}')
        except json.JSONDecodeError:
            d['data'] = {}
        return d

    # ---------- 状态快照 ----------

    def save_state(self, state) -> int:
        """保存 GameState 快照，返回自增 id。"""
        payload = json.dumps(state, ensure_ascii=False, default=str)
        with self._lock:
            cur = self._conn.execute(
                'INSERT INTO state_snapshots (timestamp, game_name, payload) '
                'VALUES (?, ?, ?)',
                (time.time(), getattr(state, 'game_name', 'unknown'), payload),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                'SELECT * FROM state_snapshots ORDER BY id DESC LIMIT ?', (limit,)
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                try:
                    d['payload'] = json.loads(d['payload'])
                except json.JSONDecodeError:
                    pass
                out.append(d)
            return out

    # ---------- 决策审计 ----------

    def save_decision(self, decision, state=None):
        actions = [a.model_dump() if hasattr(a, 'model_dump') else a for a in decision.actions]
        state_json = json.dumps(
            state.model_dump() if hasattr(state, 'model_dump') else state,
            ensure_ascii=False, default=str,
        ) if state is not None else None
        with self._lock:
            self._conn.execute(
                'INSERT INTO decisions (timestamp, game_name, reason, confidence, actions, state) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    time.time(), decision.game_name, decision.reason,
                    decision.confidence, json.dumps(actions, ensure_ascii=False, default=str),
                    state_json,
                ),
            )
            self._conn.commit()

    def save_diagnosis(self, diagnosis):
        self.add_log(
            'info', 'diagnosis',
            f'诊断: 警告 {len(diagnosis.warnings)} 条, 建议 {len(diagnosis.recommendations)} 条',
            {'recommendations': diagnosis.recommendations, 'warnings': diagnosis.warnings},
        )

    def save_execution(self, result):
        self.add_log(
            'info' if result.success else 'error', 'execution',
            f'执行 {result.actions_executed} 个操作, 成功={result.success}',
            {'errors': result.errors},
        )

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
