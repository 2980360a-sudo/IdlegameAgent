# IdleAgent - core/settings.py
# 全局应用设置（键值对，SQLite 持久化）：模型 API 配置等。

import os
import sqlite3
import threading
from typing import Dict, Optional


class SettingsStore:
    """线程安全的全局键值设置存储（app_settings 表）。"""

    def __init__(self, db_path: str = None):
        db_path = db_path or os.environ.get(
            'SETTINGS_DB', os.path.join('state', 'settings.db')
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
                'CREATE TABLE IF NOT EXISTS app_settings ('
                'key TEXT PRIMARY KEY, value TEXT)'
            )
            self._conn.commit()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                'SELECT value FROM app_settings WHERE key = ?', (key,)
            ).fetchone()
            return row['value'] if row else default

    def set(self, key: str, value: str):
        with self._lock:
            self._conn.execute(
                'INSERT INTO app_settings (key, value) VALUES (?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
                (key, value),
            )
            self._conn.commit()

    # ---------- 模型 API 配置 ----------

    def get_llm_config(self) -> Dict[str, str]:
        """返回 {api_key, model, base_url}，未设置则回退到环境变量。"""
        return {
            'api_key': self.get('llm_api_key') or os.environ.get('LLM_API_KEY', ''),
            'model': self.get('llm_model') or os.environ.get('LLM_MODEL', 'deepseek-chat'),
            'base_url': self.get('llm_base_url') or os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com'),
        }

    def set_llm_config(self, api_key: str = None, model: str = None, base_url: str = None):
        if api_key is not None:
            self.set('llm_api_key', api_key)
        if model is not None:
            self.set('llm_model', model)
        if base_url is not None:
            self.set('llm_base_url', base_url)

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


# 进程级单例
_settings_store: Optional[SettingsStore] = None


def get_settings_store() -> SettingsStore:
    global _settings_store
    if _settings_store is None:
        _settings_store = SettingsStore()
    return _settings_store
