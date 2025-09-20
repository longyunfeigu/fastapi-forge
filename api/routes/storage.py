"""存储/文件上传相关路由。"""
from __future__ import annotations

from os.path import splitext
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)

from api.dependencies import (
    get_current_active_user,
    get_file_asset_service,
)
from application.dto import (
    UserResponseDTO,
    PresignUploadRequestDTO,
    CompleteUploadRequestDTO,
    StorageUploadResponseDTO,
    PresignUploadResponseDTO,
    PresignUploadDetailDTO,
)
from application.services.file_asset_service import FileAssetApplicationService
from core.response import (
    Response as ApiResponse,
    success_response,
)
 


router = APIRouter(
    prefix="/storage",
    tags=["文件存储"],
)



@router.post(
    "/presign-upload",
    summary="生成直传预签名",
    response_model=ApiResponse[PresignUploadResponseDTO],
)
async def presign_upload(
    payload: PresignUploadRequestDTO,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
    current_user: UserResponseDTO = Depends(get_current_active_user),
):
    try:
        file_summary, presigned = await service.presign_upload(
            user_id=current_user.id,
            filename=payload.filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            kind=payload.kind,
            method=payload.method or "PUT",
            expires_in=payload.expires_in,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    response_data = PresignUploadResponseDTO(
        file=file_summary,
        upload=PresignUploadDetailDTO(
            url=presigned.url,
            method=presigned.method,
            headers=presigned.headers,
            fields=presigned.fields,
            expires_in=presigned.expires_in,
        ),
    )
    return success_response(data=response_data, message="预签名生成成功")


@router.post(
    "/complete",
    summary="直传完成确认",
    response_model=ApiResponse[dict],
)
async def confirm_presigned_upload(
    payload: CompleteUploadRequestDTO,
    service: FileAssetApplicationService = Depends(get_file_asset_service),
    current_user: UserResponseDTO = Depends(get_current_active_user),
):
    try:
        payload.ensure_identifier()
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.id is not None:
        asset = await service.get_asset_raw(payload.id)
    elif payload.key:
        asset = await service.get_asset_by_key_raw(payload.key)
    else:  # pragma: no cover - already guarded
        raise HTTPException(status_code=400, detail="缺少文件标识")

    if not current_user.is_superuser and asset.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该文件")

    await service.confirm_direct_upload(asset_id=asset.id)

    return success_response(data={"ok": True}, message="文件已激活")


@router.post(
    "/upload",
    summary="中转上传单个文件",
    response_model=ApiResponse[StorageUploadResponseDTO],
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    kind: str = Query("uploads", description="业务分类（如 avatar、document 等）"),
    service: FileAssetApplicationService = Depends(get_file_asset_service),
    current_user: UserResponseDTO = Depends(get_current_active_user),
):
    """由应用服务器中转上传文件到对象存储（编排已下沉到 Application Service）。"""
    data = await file.read()
    resp = await service.relay_upload(
        user_id=current_user.id,
        file_bytes=data,
        filename=file.filename or "upload.bin",
        kind=kind,
        content_type=file.content_type,
    )
    return success_response(data=resp, message="文件上传成功")
