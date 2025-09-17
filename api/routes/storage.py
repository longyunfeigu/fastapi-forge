"""
存储/文件上传 API 路由
"""
from typing import Optional
from os.path import splitext

from fastapi import APIRouter, UploadFile, File, Depends, Query

from api.dependencies import get_current_active_user
from application.dto import UserResponseDTO
from core.response import success_response, Response as ApiResponse
from infrastructure.external.storage import (
    get_storage,
    StorageProvider,
    key_builder,
    guess_content_type,
)
from infrastructure.external.storage.models import UploadResult


router = APIRouter(
    prefix="/storage",
    tags=["文件存储"]
)


@router.post(
    "/upload",
    summary="上传单个文件",
    response_model=ApiResponse[UploadResult],
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    kind: str = Query("uploads", description="业务分类（如 avatar、document 等）"),
    storage: StorageProvider = Depends(get_storage),
    current_user: UserResponseDTO = Depends(get_current_active_user),
):
    """上传单个文件到配置的存储后端并返回上传结果。"""
    # 解析扩展名与内容类型
    _, ext = splitext(file.filename or "")
    content_type = file.content_type or guess_content_type(file.filename or "")

    # 生成存储 key：按日期/分类/用户ID 分层
    key = key_builder(kind=kind, user_id=str(current_user.id), ext=ext)

    # 读取文件并上传
    data = await file.read()
    metadata = {"filename": file.filename or ""}
    result = await storage.upload(data, key, metadata=metadata, content_type=content_type)

    # 若后端未返回 URL，则尝试派生公共 URL
    if not result.url:
        url = storage.public_url(result.key)
        if url:
            result = result.model_copy(update={"url": url})

    return success_response(data=result, message="文件上传成功")

