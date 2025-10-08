"""WebSocket routes for realtime features.

Enhancements:
- Add heartbeat/idle-timeout handling to detect half-open connections.
- Server sends JSON ping on idle; closes after configurable missed pongs.
"""
from __future__ import annotations

from typing import Any
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from application.services.realtime_service import RealtimeService
from application.ports.realtime import Envelope
from application.services.user_service import UserApplicationService
from application.services.token_service import TokenService
from core.logging_config import get_logger
from core.i18n import t, get_locale, set_locale
from api.dependencies import get_user_service, get_token_service
from core.config import settings


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
    token_service: TokenService = Depends(get_token_service),
) -> None:
    await ws.accept()
    # Parse locale for WS (since LocaleMiddleware doesn't run for websockets)
    ws_lang = ws.query_params.get("lang") or ws.headers.get("X-Lang") or ""
    if not ws_lang:
        al = ws.headers.get("Accept-Language") or ""
        if al:
            # naive parse: take first tag
            ws_lang = al.split(",")[0].strip()
    if ws_lang:
        set_locale(ws_lang)
    # Authenticate
    token = _extract_token(ws)
    if not token:
        await ws.close(code=1008)
        return
    try:
        user_id = await token_service.verify_access_token(token)
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
    # Handle connection through RealtimeService for consistent architecture
    await rt.connect(user_id, ws, is_superuser=current_user.is_superuser)
    try:
        # Heartbeat/idle detection parameters (configurable via .env)
        idle_ping_interval = float(getattr(settings, "REALTIME_WS_IDLE_PING_INTERVAL_S", 30.0))
        pong_grace = float(getattr(settings, "REALTIME_WS_PONG_GRACE_S", 10.0))
        missed_limit = int(getattr(settings, "REALTIME_WS_MISSED_PING_LIMIT", 2))

        missed = 0
        while True:
            if idle_ping_interval and idle_ping_interval > 0:
                try:
                    msg = await asyncio.wait_for(ws.receive_json(), timeout=idle_ping_interval)
                except asyncio.TimeoutError:
                    # Idle: send ping and wait a short grace for response
                    missed += 1
                    try:
                        await ws.send_json(Envelope(type="ping").model_dump())
                    except Exception:
                        # If send fails, treat as disconnected
                        await ws.close(code=1001)
                        break
                    try:
                        msg = await asyncio.wait_for(ws.receive_json(), timeout=pong_grace)
                        # Received something after ping (pong or normal message)
                        missed = 0
                    except asyncio.TimeoutError:
                        if missed > missed_limit:
                            await ws.close(code=1001)
                            break
                        else:
                            # Continue waiting; send next ping on next idle interval
                            continue
            else:
                # Idle ping disabled: wait indefinitely for next message
                msg = await ws.receive_json()
            mtype = str(msg.get("type") or "").lower()
            if mtype == "join":
                room = str(msg.get("room") or "").strip()
                if not room:
                    await ws.send_json(Envelope(
                        type="error",
                        data={
                            "message": t("ws.error.room_required"),
                            "message_key": "ws.error.room_required",
                            "locale": get_locale(),
                        },
                    ).model_dump())
                    continue
                try:
                    await rt.join_room(user_id, room, ws, is_superuser=current_user.is_superuser)
                except PermissionError:
                    await ws.send_json(Envelope(
                        type="error",
                        data={
                            "message": t("ws.error.forbidden"),
                            "message_key": "ws.error.forbidden",
                            "locale": get_locale(),
                        },
                    ).model_dump())
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
                    await ws.send_json(Envelope(
                        type="error",
                        data={
                            "message": t("ws.error.forbidden"),
                            "message_key": "ws.error.forbidden",
                            "locale": get_locale(),
                        },
                    ).model_dump())
            elif mtype == "ping":
                await ws.send_json(Envelope(type="pong").model_dump())
            elif mtype == "pong":
                # Client heartbeat reply; nothing else to do.
                continue
            else:
                await ws.send_json(Envelope(
                    type="error",
                    data={
                        "message": t("ws.error.unknown_type"),
                        "message_key": "ws.error.unknown_type",
                        "locale": get_locale(),
                    },
                ).model_dump())
    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=user_id)
    except Exception as exc:
        logger.error("ws_error", user_id=user_id, error=str(exc), exc_info=True)
    finally:
        await rt.disconnect(user_id, ws)
