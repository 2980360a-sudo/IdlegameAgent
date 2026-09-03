"""Melvor 挂机 Agent 路由：登录云账号、选择角色、三种模式启停、状态与日志。"""
import os
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.routes.auth import get_current_user
from core.melvor_agent import (
    MelvorAgentSession, MelvorAccountStore, RUN_MODE_LABELS, RUN_MODE_DESC,
)
from core.llm import LLMClient
from core.storage import Storage

router = APIRouter()

account_store = MelvorAccountStore()
storage = Storage()
_sessions: Dict[int, MelvorAgentSession] = {}

USE_REAL_ADAPTER = os.environ.get('USE_REAL_ADAPTER', 'false').lower() == 'true'


def _get_session(user_id: int) -> MelvorAgentSession:
    """惰性创建每用户会话；真实/模拟取决于 USE_REAL_ADAPTER。"""
    if user_id not in _sessions:
        mock = not USE_REAL_ADAPTER
        adapter = None
        if not mock:
            try:
                from adapters.melvor_idle import MelvorIdleAdapter
                adapter = MelvorIdleAdapter()
            except Exception as e:
                print(f'[Melvor] 适配器初始化失败: {e}')
        llm = LLMClient() if LLMClient().configured else None
        _sessions[user_id] = MelvorAgentSession(
            user_id, adapter=adapter, llm=llm, storage=storage, mock=mock,
        )
    return _sessions[user_id]


# ------------------------------------------------------------
# 请求模型
# ------------------------------------------------------------
class LoginRequest(BaseModel):
    account: str = Field(..., description='Melvor 云账号')
    password: str = Field(..., description='密码')


class SelectRequest(BaseModel):
    index: int = Field(..., description='角色（存档槽）索引')


class StartRequest(BaseModel):
    mode: str = Field(..., description='efficiency | survival | manual')
    script: Optional[List[Dict[str, Any]]] = Field(None, description='manual 模式脚本')


class ScriptRequest(BaseModel):
    script: List[Dict[str, Any]] = Field(..., description='manual 模式脚本（动作列表）')


# ------------------------------------------------------------
# 路由
# ------------------------------------------------------------
@router.get('/melvor/modes')
async def list_modes():
    return {
        'modes': [
            {'value': k, 'label': RUN_MODE_LABELS[k], 'description': RUN_MODE_DESC[k]}
            for k in RUN_MODE_LABELS
        ]
    }


@router.get('/melvor/config')
async def get_config(user: dict = Depends(get_current_user)):
    return {'config': account_store.get_public(user['id']) or {}}


@router.post('/melvor/login')
async def melvor_login(req: LoginRequest, user: dict = Depends(get_current_user)):
    account_store.save(user['id'], account=req.account, password=req.password)
    session = _get_session(user['id'])
    result = await session.login(req.account, req.password)
    if not result.get('ok'):
        raise HTTPException(status_code=400, detail=result.get('error', '登录失败'))
    return result


@router.post('/melvor/auto_login')
async def melvor_auto_login(user: dict = Depends(get_current_user)):
    """用已持久化的云账号自动登录（无需重新输入密码）。"""
    saved = account_store.get(user['id'])
    if not saved or not saved.get('account') or not saved.get('password'):
        return {'ok': False, 'error': '未保存云账号'}
    session = _get_session(user['id'])
    result = await session.login(saved['account'], saved['password'])
    if not result.get('ok'):
        raise HTTPException(status_code=400, detail=result.get('error', '自动登录失败'))
    return result


@router.post('/melvor/auto_resume')
async def melvor_auto_resume(user: dict = Depends(get_current_user)):
    """一键恢复：用已存账号登录 → 选已存角色 → 启动已存模式（全自动挂机）。"""
    saved = account_store.get(user['id'])
    if not saved or not saved.get('account') or not saved.get('password'):
        return {'ok': False, 'error': '未保存云账号'}
    session = _get_session(user['id'])
    out: Dict[str, Any] = {'ok': True}

    # 1. 登录
    r = await session.login(saved['account'], saved['password'])
    if not r.get('ok'):
        raise HTTPException(status_code=400, detail=r.get('error', '登录失败'))
    out['login'] = True
    out['characters'] = r.get('characters', [])

    # 2. 选角色（若已保存）
    if saved.get('character_index') is not None:
        r = await session.select_character(saved['character_index'])
        out['select'] = bool(r.get('ok'))

    # 3. 启动（若已保存模式）
    if saved.get('mode'):
        script = saved.get('script') if saved.get('mode') == 'manual' else None
        r = await session.start(saved['mode'], script)
        out['start'] = bool(r.get('ok'))
        out['mode'] = saved['mode']

    return out


@router.get('/melvor/characters')
async def list_characters(user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    return {'characters': await session.list_characters()}


@router.post('/melvor/select')
async def select_character(req: SelectRequest, user: dict = Depends(get_current_user)):
    account_store.save(user['id'], character_index=req.index)
    session = _get_session(user['id'])
    result = await session.select_character(req.index)
    if not result.get('ok'):
        raise HTTPException(status_code=400, detail=result.get('error', '选择角色失败'))
    return result


@router.post('/melvor/start')
async def start_agent(req: StartRequest, user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    if session.character_index is None and not USE_REAL_ADAPTER:
        # 模拟模式下允许直接启动（无需真实选角色）；真实模式需先选角色
        pass
    account_store.save(user['id'], mode=req.mode, script=req.script)
    result = await session.start(req.mode, req.script)
    if not result.get('ok'):
        raise HTTPException(status_code=400, detail=result.get('error', '启动失败'))
    return result


@router.post('/melvor/stop')
async def stop_agent(user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    return await session.stop()


@router.post('/melvor/disconnect')
async def disconnect_agent(user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    await session.disconnect()
    return {'ok': True}


@router.get('/melvor/status')
async def melvor_status(user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    return await session.get_status()


@router.get('/melvor/events')
async def melvor_events(limit: int = 100, user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    return {'events': session.get_events(limit)}


@router.get('/melvor/decisions')
async def melvor_decisions(limit: int = 100, user: dict = Depends(get_current_user)):
    session = _get_session(user['id'])
    return {'decisions': session.get_decisions(limit)}


@router.post('/melvor/script')
async def save_script(req: ScriptRequest, user: dict = Depends(get_current_user)):
    account_store.save(user['id'], script=req.script)
    session = _get_session(user['id'])
    session._script = req.script
    return {'ok': True, 'script': req.script}
