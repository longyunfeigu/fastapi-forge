from __future__ import annotations

from typing import Optional

from google.protobuf import empty_pb2, timestamp_pb2, wrappers_pb2

from application.dto import UserResponseDTO
from grpc_app.generated.forge.v1 import user_pb2


def _to_timestamp(dt: Optional[object]) -> Optional[timestamp_pb2.Timestamp]:
    if not dt:
        return None
    ts = timestamp_pb2.Timestamp()
    try:
        # dt is a datetime with tzinfo
        ts.FromDatetime(dt)
    except Exception:
        return None
    return ts


def user_dto_to_proto(dto: UserResponseDTO) -> user_pb2.User:
    msg = user_pb2.User(
        id=int(dto.id),
        username=dto.username,
        email=dto.email or "",
        phone=dto.phone or "",
        full_name=dto.full_name or "",
        is_active=bool(dto.is_active),
        is_superuser=bool(dto.is_superuser),
    )
    if dto.created_at:
        ts = _to_timestamp(dto.created_at)
        if ts:
            msg.created_at.CopyFrom(ts)
    if dto.updated_at:
        ts = _to_timestamp(dto.updated_at)
        if ts:
            msg.updated_at.CopyFrom(ts)
    if dto.last_login:
        ts = _to_timestamp(dto.last_login)
        if ts:
            msg.last_login.CopyFrom(ts)
    return msg


def str_to_wrapper(value: Optional[str]) -> wrappers_pb2.StringValue | None:
    if value is None:
        return None
    return wrappers_pb2.StringValue(value=value)


Empty = empty_pb2.Empty  # alias

