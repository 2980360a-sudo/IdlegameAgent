# IdleAgent v0.5.0 - core/auth.py
# 用户认证核心：密码哈希 + 签名 token + SQLite 用户存储（无第三方依赖）

import os
import json
import time
import hmac
import base64
import hashlib
import secrets
import sqlite3
import threading
from typing import Optional, Dict, Any, List

# 项目根目录（core/ 的上一级），保证数据文件路径稳定
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------
# 密码哈希（PBKDF2-SHA256，内置实现，无需 passlib/bcrypt）
# ------------------------------------------------------------
PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """生成 PBKDF2-SHA256 密码哈希，格式: pbkdf2_sha256$iters$salt_b64$hash_b64"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return 'pbkdf2_sha256${}${}${}'.format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(dk).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    """校验密码（常数时间比较）。"""
    try:
        algo, iters, salt_b64, hash_b64 = stored.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


# ------------------------------------------------------------
# 签名 Token（JWT 风格，HMAC-SHA256，无第三方依赖）
# ------------------------------------------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def _b64url_decode(s: str) -> bytes:
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _load_or_create_secret() -> str:
    """优先读取 SECRET_KEY 环境变量；否则从 state/secret.key 载入或生成并持久化。"""
    env_secret = os.environ.get('SECRET_KEY', '')
    if env_secret:
        return env_secret
    key_file = os.path.join(_PROJECT_ROOT, 'state', 'secret.key')
    try:
        if os.path.exists(key_file):
            with open(key_file, 'r', encoding='utf-8') as f:
                secret = f.read().strip()
                if secret:
                    return secret
    except Exception:
        pass
    secret = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(key_file) or '.', exist_ok=True)
        with open(key_file, 'w', encoding='utf-8') as f:
            f.write(secret)
    except Exception:
        pass
    return secret


class TokenManager:
    """签发与校验 HMAC 签名 token。"""

    def __init__(self, secret: str = None):
        self.secret = secret or _load_or_create_secret()

    def sign(self, payload: Dict[str, Any], expires_in: int = 7 * 24 * 3600) -> str:
        now = int(time.time())
        body = {**payload, 'exp': now + expires_in, 'iat': now}
        header_b64 = _b64url_encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
        payload_b64 = _b64url_encode(json.dumps(body, separators=(',', ':')).encode())
        msg = f'{header_b64}.{payload_b64}'.encode()
        sig = hmac.new(self.secret.encode(), msg, hashlib.sha256).digest()
        return f'{header_b64}.{payload_b64}.{_b64url_encode(sig)}'

    def verify(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            header_b64, payload_b64, sig_b64 = token.split('.')
            msg = f'{header_b64}.{payload_b64}'.encode()
            expected = hmac.new(self.secret.encode(), msg, hashlib.sha256).digest()
            if not hmac.compare_digest(_b64url_decode(sig_b64), expected):
                return None
            body = json.loads(_b64url_decode(payload_b64))
            if body.get('exp', 0) < int(time.time()):
                return None
            return body
        except Exception:
            return None


# ------------------------------------------------------------
# 用户存储（SQLite）
# ------------------------------------------------------------
class UserExistsError(Exception):
    """用户名或邮箱已存在。"""


class UserStore:
    """用户信息持久化（SQLite，线程安全）。"""

    def __init__(self, db_path: str = None):
        db_path = db_path or os.environ.get(
            'USERS_DB', os.path.join(_PROJECT_ROOT, 'state', 'users.db')
        )
        directory = os.path.dirname(db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # 使用可重入锁：create_user/update_user 在持锁时会调用 get_by_id（再次加锁）
        self._lock = threading.RLock()
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    profile TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    @staticmethod
    def _public(row: sqlite3.Row) -> Dict[str, Any]:
        """脱敏：不返回 password_hash。"""
        if row is None:
            return None
        d = dict(row)
        d.pop('password_hash', None)
        try:
            d['profile'] = json.loads(d.get('profile') or '{}')
        except json.JSONDecodeError:
            d['profile'] = {}
        return d

    def create_user(self, username: str, email: str, password: str,
                    display_name: str = None, profile: Dict = None) -> Dict[str, Any]:
        username = (username or '').strip()
        email = (email or '').strip().lower() or None
        if not username:
            raise ValueError('用户名不能为空')
        if not password or len(password) < 6:
            raise ValueError('密码至少 6 位')
        now = time.time()
        try:
            with self._lock:
                cur = self._conn.execute(
                    "INSERT INTO users (username, email, password_hash, display_name, profile, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        username,
                        email,
                        hash_password(password),
                        (display_name or '').strip() or username,
                        json.dumps(profile or {}, ensure_ascii=False),
                        now,
                        now,
                    ),
                )
                self._conn.commit()
                return self.get_by_id(cur.lastrowid)
        except sqlite3.IntegrityError:
            raise UserExistsError('用户名或邮箱已被注册')

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM users WHERE id = ?', (user_id,)
            ).fetchone()
        return self._public(row)

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM users WHERE username = ?', ((username or '').strip(),)
            ).fetchone()
        return self._public(row)

    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM users WHERE email = ?', ((email or '').strip().lower(),)
            ).fetchone()
        return self._public(row)

    def _get_row_by_login(self, login: str) -> Optional[sqlite3.Row]:
        login = (login or '').strip()
        if not login:
            return None
        with self._lock:
            row = self._conn.execute(
                'SELECT * FROM users WHERE username = ? OR email = ?', (login, login.lower())
            ).fetchone()
        return row

    def verify_credentials(self, login: str, password: str) -> Optional[Dict[str, Any]]:
        """用用户名或邮箱登录。"""
        row = self._get_row_by_login(login)
        if row is None:
            return None
        if not verify_password(password or '', row['password_hash']):
            return None
        return self.get_by_id(row['id'])

    def update_user(self, user_id: int, display_name: str = None, email: str = None,
                    profile: Dict = None, password: str = None) -> Optional[Dict[str, Any]]:
        """更新用户信息；传 None 的字段保持不变。"""
        with self._lock:
            row = self._conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if row is None:
                return None
            new_display = row['display_name'] if display_name is None else (display_name or '').strip()
            new_email = row['email'] if email is None else ((email or '').strip().lower() or None)
            new_profile = row['profile'] if profile is None else json.dumps(profile, ensure_ascii=False)
            new_hash = row['password_hash'] if password is None else hash_password(password)
            try:
                self._conn.execute(
                    "UPDATE users SET display_name = ?, email = ?, profile = ?, password_hash = ?, updated_at = ? "
                    "WHERE id = ?",
                    (new_display, new_email, new_profile, new_hash, time.time(), user_id),
                )
                self._conn.commit()
            except sqlite3.IntegrityError:
                raise UserExistsError('邮箱已被占用')
        return self.get_by_id(user_id)

    def count(self) -> int:
        with self._lock:
            return self._conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]

    def close(self):
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
