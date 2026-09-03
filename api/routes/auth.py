"""用户认证路由：注册 / 登录 / 登出 / 我的信息 / 更新资料。"""
import os
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from core.auth import UserStore, TokenManager, UserExistsError

router = APIRouter()

user_store = UserStore()
token_manager = TokenManager()
_bearer = HTTPBearer(auto_error=False)

# 本地版关闭认证：无需注册/登录，直接以「本地用户」身份使用（用户数据存 user_id=1）
DISABLE_AUTH = os.environ.get('DISABLE_AUTH', 'false').lower() == 'true'
LOCAL_USER = {
    'id': 1, 'username': 'local', 'display_name': '本地用户',
    'email': None, 'profile': {}, 'created_at': 0,
}


# ------------------------------------------------------------
# 请求/响应模型
# ------------------------------------------------------------
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=32, description='用户名')
    email: str = Field('', description='邮箱（可选）')
    password: str = Field(..., min_length=6, max_length=128, description='密码')
    display_name: str = Field('', description='昵称（可选）')


class LoginRequest(BaseModel):
    login: str = Field(..., description='用户名或邮箱')
    password: str


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    profile: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------
# 认证依赖
# ------------------------------------------------------------
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict[str, Any]:
    if DISABLE_AUTH:
        return dict(LOCAL_USER)
    if credentials is None:
        raise HTTPException(status_code=401, detail='未登录')
    payload = token_manager.verify(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail='登录已过期，请重新登录')
    user = user_store.get_by_id(payload.get('sub'))
    if user is None:
        raise HTTPException(status_code=401, detail='用户不存在')
    return user


# ------------------------------------------------------------
# 路由
# ------------------------------------------------------------
@router.post('/auth/register', status_code=201)
async def register(req: RegisterRequest):
    try:
        user = user_store.create_user(
            username=req.username,
            email=req.email,
            password=req.password,
            display_name=req.display_name,
        )
    except UserExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = token_manager.sign({'sub': user['id'], 'username': user['username']})
    return {'token': token, 'user': user}


@router.post('/auth/login')
async def login(req: LoginRequest):
    user = user_store.verify_credentials(req.login, req.password)
    if user is None:
        raise HTTPException(status_code=401, detail='用户名或密码错误')
    token = token_manager.sign({'sub': user['id'], 'username': user['username']})
    return {'token': token, 'user': user}


@router.post('/auth/logout')
async def logout():
    # 无状态 token，客户端丢弃即可；保留端点以便前端统一调用
    return {'status': 'ok', 'message': '已登出'}


@router.get('/auth/me')
async def me(user: Dict[str, Any] = Depends(get_current_user)):
    return {'user': user}


@router.patch('/auth/me')
async def update_me(req: UpdateProfileRequest, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        updated = user_store.update_user(
            user['id'],
            display_name=req.display_name,
            email=req.email,
            profile=req.profile,
            password=req.password,
        )
    except UserExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {'user': updated}
