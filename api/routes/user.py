"""
用户API路由 - FastAPI表现层
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Security, Request
from typing import Any
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional

from application.services.user_service import UserApplicationService
from core.response import success_response, paginated_response, Response as ApiResponse, PaginatedData
from application.dto import (
    UserCreateDTO, UserUpdateDTO, UserResponseDTO,
    LoginDTO, TokenDTO, ChangePasswordDTO,
    MessageDTO, PaginationParams, RefreshTokenDTO
)
from api.dependencies import (
    get_current_active_user,
    get_current_superuser,
    get_user_service,
)
from core.i18n import t
from domain.common.exceptions import UserNotFoundException

router = APIRouter(
    prefix="/users",
    tags=["用户管理"]
)
@router.post("/register", summary="用户注册", response_model=ApiResponse[UserResponseDTO])
async def register(
    user_data: UserCreateDTO,
    service: UserApplicationService = Depends(get_user_service)
):
    """
    注册新用户
    
    - **username**: 用户名（3-20个字符，只能包含字母、数字和下划线）
    - **email**: 邮箱地址
    - **password**: 密码（至少8位，包含大小写字母和数字）
    - **full_name**: 全名（可选）
    - **phone**: 手机号（可选，中国手机号格式）
    """
    user = await service.register_user(user_data)
    return success_response(data=user, message=t("user.register.success"))


@router.post("/login", summary="用户登录", response_model=TokenDTO)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserApplicationService = Depends(get_user_service)
):
    """
    用户登录获取访问令牌

    支持用户名或邮箱登录

    支持刷新令牌轮转（Refresh Token Rotation）：
    - 每次刷新时旧令牌失效
    - 检测令牌重用攻击
    - 追踪设备和IP
    """
    login_data = LoginDTO(
        username=form_data.username,
        password=form_data.password
    )
    # 提取设备信息和IP
    device_info = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    token = await service.login(
        login_data,
        device_info=device_info,
        ip_address=ip_address
    )
    # 返回扁平结构，符合 OAuth2 密码模式的期望
    return token


@router.post("/refresh", summary="刷新访问令牌", response_model=TokenDTO)
async def refresh(
    request: Request,
    body: RefreshTokenDTO,
    service: UserApplicationService = Depends(get_user_service)
):
    """
    使用刷新令牌换取新的访问令牌

    刷新令牌轮转（Refresh Token Rotation）：
    - 旧刷新令牌立即失效，返回新的刷新令牌
    - 防止令牌重放攻击
    - 如果检测到已使用的令牌被再次使用，撤销整个令牌家族
    """
    device_info = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    return await service.refresh_token(
        body.refresh_token,
        device_info=device_info,
        ip_address=ip_address
    )


@router.get("/me", summary="获取当前用户信息", response_model=ApiResponse[UserResponseDTO])
async def get_current_user_info(
    current_user: UserResponseDTO = Depends(get_current_active_user)
):
    """获取当前登录用户的信息"""
    return success_response(data=current_user, message=t("user.get.success"))


@router.put("/me", summary="更新当前用户信息", response_model=ApiResponse[UserResponseDTO])
async def update_current_user(
    update_data: UserUpdateDTO,
    current_user: UserResponseDTO = Depends(get_current_active_user),
    service: UserApplicationService = Depends(get_user_service)
):
    """更新当前用户的个人信息"""
    updated_user = await service.update_user(current_user.id, update_data)
    return success_response(data=updated_user, message=t("user.update.success"))


@router.post("/me/change-password", summary="修改密码", response_model=ApiResponse[Any])
async def change_password(
    password_data: ChangePasswordDTO,
    current_user: UserResponseDTO = Depends(get_current_active_user),
    service: UserApplicationService = Depends(get_user_service)
):
    """修改当前用户的密码"""
    await service.change_password(current_user.id, password_data)
    return success_response(data=None, message=t("user.password.change.success"))


@router.get(
    "/",
    summary="获取用户列表",
    response_model=ApiResponse[PaginatedData[UserResponseDTO]],
)
async def list_users(
    params: PaginationParams = Depends(),
    is_active: Optional[bool] = Query(None, description="筛选激活状态"),
    service: UserApplicationService = Depends(get_user_service),
    _current_user: UserResponseDTO = Security(get_current_superuser)
):
    """
    获取用户列表（需要超级管理员权限）
    
    支持分页和按激活状态筛选
    """
    users, total = await service.list_users(params.skip, params.limit, is_active)
    page = params.page
    return paginated_response(
        items=users,
        total=total,
        page=page,
        size=params.limit,
        message=t("user.list.success")
    )


@router.get("/{user_id}", summary="获取指定用户信息", response_model=ApiResponse[UserResponseDTO])
async def get_user(
    user_id: int,
    service: UserApplicationService = Depends(get_user_service),
    _current_user: UserResponseDTO = Security(get_current_superuser)
):
    """获取指定用户的信息（需要超级管理员权限）"""
    user = await service.get_user(user_id)
    return success_response(data=user, message=t("user.get.success"))


@router.put("/{user_id}", summary="更新用户信息", response_model=ApiResponse[UserResponseDTO])
async def update_user(
    user_id: int,
    update_data: UserUpdateDTO,
    service: UserApplicationService = Depends(get_user_service),
    _current_user: UserResponseDTO = Security(get_current_superuser)
):
    """更新指定用户的信息（需要超级管理员权限）"""
    updated_user = await service.update_user(user_id, update_data)
    return success_response(data=updated_user, message=t("user.update.success"))


@router.put("/{user_id}/activate", summary="激活用户", response_model=ApiResponse[UserResponseDTO])
async def activate_user(
    user_id: int,
    service: UserApplicationService = Depends(get_user_service),
    _current_user: UserResponseDTO = Security(get_current_superuser)
):
    """激活指定用户（需要超级管理员权限）"""
    activated_user = await service.activate_user(user_id)
    return success_response(data=activated_user, message=t("user.activate.success"))


@router.put("/{user_id}/deactivate", summary="停用用户", response_model=ApiResponse[UserResponseDTO])
async def deactivate_user(
    user_id: int,
    service: UserApplicationService = Depends(get_user_service),
    _current_user: UserResponseDTO = Security(get_current_superuser)
):
    """停用指定用户（需要超级管理员权限）"""
    deactivated_user = await service.deactivate_user(user_id)
    return success_response(data=deactivated_user, message=t("user.deactivate.success"))


@router.delete("/{user_id}", summary="删除用户", response_model=ApiResponse[Any])
async def delete_user(
    user_id: int,
    service: UserApplicationService = Depends(get_user_service),
    _current_user: UserResponseDTO = Security(get_current_superuser)
):
    """删除指定用户（需要超级管理员权限）"""
    success = await service.delete_user(user_id)
    if not success:
        # 统一使用领域异常，以便全局异常处理器映射与国际化
        raise UserNotFoundException(str(user_id))
    return success_response(data=None, message=t("user.delete.success"))



@router.get("/me/sessions", summary="获取活跃会话列表", response_model=ApiResponse[Any])
async def get_active_sessions(
    current_user: UserResponseDTO = Depends(get_current_active_user),
    service: UserApplicationService = Depends(get_user_service)
):
    """
    获取当前用户的所有活跃登录会话

    返回：
    - 会话创建时间
    - 会话过期时间  
    - 设备信息（User-Agent）
    - IP地址
    """
    sessions = await service.get_active_sessions(current_user.id)
    return success_response(data=sessions, message=t("user.sessions.list.success", count=len(sessions)))


@router.post("/me/logout-all", summary="登出所有设备", response_model=ApiResponse[Any])
async def logout_all_devices(
    current_user: UserResponseDTO = Depends(get_current_active_user),
    service: UserApplicationService = Depends(get_user_service)
):
    """
    登出所有设备（撤销所有刷新令牌）

    安全功能：
    - 撤销当前用户的所有刷新令牌
    - 用于账户被盗用时紧急登出
    - 不影响已发放的访问令牌（直到过期）
    """
    count = await service.logout_all_devices(current_user.id)
    return success_response(data={"revoked_count": count}, message=t("user.logout_all.success", count=count))
