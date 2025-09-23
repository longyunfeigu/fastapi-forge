"""WebSocket routes for realtime features."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from application.services.realtime_service import RealtimeService
from application.ports.realtime import Envelope
from application.services.user_service import UserApplicationService
from core.logging_config import get_logger
from api.dependencies import get_user_service


logger = get_logger(__name__)


router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _extract_token(ws: WebSocket) -> str | None:
    # Prefer query param, fallback to header `Authorization: Bearer x`
    token = ws.query_params.get("token")
    if token:
        return token
    auth = ws.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_realtime_service_from_app(ws: WebSocket) -> RealtimeService:
    svc = getattr(ws.app.state, "realtime_service", None)
    if svc is None:
        raise RuntimeError("Realtime service not initialized. Ensure lifespan sets app.state.realtime_service.")
    return svc


@router.websocket("")
async def websocket_endpoint(
    ws: WebSocket,
    user_service: UserApplicationService = Depends(get_user_service),
) -> None:
    await ws.accept()
    # Authenticate
    token = _extract_token(ws)
    if not token:
        await ws.close(code=1008)
        return
    try:
        user_id = await user_service.verify_token(token)
    except Exception:
        # TokenExpired handled by HTTP routes; here we simply deny
        user_id = None
    if not user_id:
        await ws.close(code=1008)
        return

    rt = get_realtime_service_from_app(ws)
    # 获取当前用户信息（用于 ACL，如是否超管）
    try:
        current_user = await user_service.get_user(user_id)
    except Exception:
        await ws.close(code=1008)
        return
    # Minimal presence state: connected (rooms handled by client join)
    await rt.connections.add(user_id, ws)
    try:
        while True:
            msg = await ws.receive_json()
            mtype = str(msg.get("type") or "").lower()
            if mtype == "join":
                room = str(msg.get("room") or "").strip()
                if not room:
                    await ws.send_json(Envelope(type="error", data={"message": "room required"}).model_dump())
                    continue
                try:
                    await rt.join_room(user_id, room, ws, is_superuser=current_user.is_superuser)
                except PermissionError:
                    await ws.send_json(Envelope(type="error", data={"message": "forbidden"}).model_dump())
            elif mtype == "leave":
                room = str(msg.get("room") or "").strip()
                if room:
                    await rt.leave_room(user_id, room, ws)
            elif mtype == "message":
                room = str(msg.get("room") or "").strip()
                payload: dict[str, Any] = {}
                if "data" in msg and isinstance(msg["data"], dict):
                    payload = msg["data"]
                elif "text" in msg:
                    payload = {"text": msg.get("text")}
                try:
                    await rt.send_message(user_id, room, payload, is_superuser=current_user.is_superuser)
                except PermissionError:
                    await ws.send_json(Envelope(type="error", data={"message": "forbidden"}).model_dump())
            elif mtype == "ping":
                await ws.send_json(Envelope(type="pong").model_dump())
            else:
                await ws.send_json(Envelope(type="error", data={"message": "unknown type"}).model_dump())
    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=user_id)
    except Exception as exc:
        logger.error("ws_error", user_id=user_id, error=str(exc), exc_info=True)
    finally:
        await rt.connections.remove(user_id, ws)
