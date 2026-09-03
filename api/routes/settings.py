"""系统设置路由：模型 API 配置（key/模型/接口地址）的读写。"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.routes.auth import get_current_user
from core.settings import get_settings_store

router = APIRouter()
store = get_settings_store()


class SettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None


def _mask_key(key: str) -> str:
    if not key:
        return ''
    if len(key) <= 8:
        return '***'
    return key[:6] + '****' + key[-4:]


def _llm_payload() -> dict:
    cfg = store.get_llm_config()
    return {
        'has_key': bool(cfg['api_key']),
        'api_key_masked': _mask_key(cfg['api_key']),
        'model': cfg['model'],
        'base_url': cfg['base_url'],
    }


@router.get('/settings')
async def get_settings(user: dict = Depends(get_current_user)):
    return {'llm': _llm_payload()}


@router.post('/settings')
async def update_settings(req: SettingsUpdate, user: dict = Depends(get_current_user)):
    if req.api_key is not None:
        store.set('llm_api_key', req.api_key)
    if req.model is not None and req.model.strip():
        store.set('llm_model', req.model.strip())
    if req.base_url is not None and req.base_url.strip():
        store.set('llm_base_url', req.base_url.strip())

    # 热更新当前会话的 LLM 客户端
    try:
        from api.routes.melvor import _sessions
        session = _sessions.get(user['id'])
        if session is not None and session.llm is not None:
            session.llm.update_config(
                api_key=(req.api_key if req.api_key is not None else None),
                model=(req.model if req.model else None),
                base_url=(req.base_url if req.base_url else None),
            )
    except Exception:
        pass

    return {'llm': _llm_payload()}
