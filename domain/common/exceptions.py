"""领域层业务异常定义，供领域与基础设施使用。

核心（core）层仅负责全局映射与异常处理，尽量避免领域层反向依赖核心层。
"""
from __future__ import annotations

from typing import Optional
from shared.codes import BusinessCode


class BusinessException(Exception):
    """业务异常基类"""

    def __init__(
        self,
        code: int,
        message: str,
        error_type: str = "BusinessError",
        details: Optional[dict] = None,
        field: Optional[str] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.error_type = error_type
        self.details = details
        self.field = field
        super().__init__(self.message)


class UserNotFoundException(BusinessException):
    def __init__(self, user_id: Optional[str] = None):
        details = {"user_id": user_id} if user_id else None
        super().__init__(
            code=BusinessCode.USER_NOT_FOUND,
            message="用户不存在",
            error_type="UserNotFound",
            details=details,
        )


class UserAlreadyExistsException(BusinessException):
    def __init__(self, email: str):
        super().__init__(
            code=BusinessCode.USER_ALREADY_EXISTS,
            message=f"邮箱 {email} 已被注册",
            error_type="UserAlreadyExists",
            details={"email": email},
            field="email",
        )


class UsernameAlreadyExistsException(BusinessException):
    def __init__(self, username: str):
        super().__init__(
            code=BusinessCode.USER_ALREADY_EXISTS,
            message=f"用户名 {username} 已被使用",
            error_type="UsernameAlreadyExists",
            details={"username": username},
            field="username",
        )


class PasswordErrorException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.PASSWORD_ERROR,
            message="用户名或密码错误",
            error_type="PasswordError",
        )


class UserInactiveException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.FORBIDDEN,
            message="用户账户已被停用",
            error_type="UserInactive",
        )


class NewPasswordSameAsOldException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="新密码不能与原密码相同",
            error_type="NewPasswordSameAsOld",
            field="new_password",
        )


class DomainValidationException(BusinessException):
    def __init__(self, message: str, *, field: str | None = None, details: dict | None = None):
        super().__init__(
            code=BusinessCode.PARAM_VALIDATION_ERROR,
            message=message,
            error_type="DomainValidationError",
            details=details,
            field=field,
        )


class SuperuserDeactivationForbiddenException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.FORBIDDEN,
            message="不能停用超级管理员账户",
            error_type="SuperuserDeactivationForbidden",
        )


class UserAlreadyActiveException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="用户已经是激活状态",
            error_type="UserAlreadyActive",
        )


class UserAlreadyInactiveException(BusinessException):
    def __init__(self):
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="用户已经是停用状态",
            error_type="UserAlreadyInactive",
        )


class FileAssetNotFoundException(BusinessException):
    def __init__(self, asset_id: Optional[int] = None, *, key: Optional[str] = None):
        details = {}
        if asset_id is not None:
            details["asset_id"] = asset_id
        if key is not None:
            details["key"] = key
        super().__init__(
            code=BusinessCode.NOT_FOUND,
            message="文件资源不存在",
            error_type="FileAssetNotFound",
            details=details or None,
        )


class FileAssetAlreadyDeletedException(BusinessException):
    def __init__(self, asset_id: Optional[int] = None):
        details = {"asset_id": asset_id} if asset_id is not None else None
        super().__init__(
            code=BusinessCode.BUSINESS_ERROR,
            message="文件已被删除",
            error_type="FileAssetAlreadyDeleted",
            details=details,
        )
