import asyncio
from typing import Tuple

import pytest


pytestmark = pytest.mark.asyncio


def _skip_if_no_generated():
    try:
        import grpc  # noqa: F401
        from grpc_app.generated.forge.v1 import user_pb2, user_pb2_grpc  # noqa: F401
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"gRPC stubs not generated or grpc not installed: {exc}")


@pytest.fixture
async def grpc_user_server() -> Tuple[str, object]:
    """Start a minimal gRPC server with a fake UserService for demo tests.

    Uses an in-process, insecure channel on an ephemeral port (port 0).
    """
    _skip_if_no_generated()

    import grpc
    from google.protobuf import empty_pb2
    from grpc_app.generated.forge.v1 import user_pb2, user_pb2_grpc

    # Simple in-memory model for demo
    class FakeUserService(user_pb2_grpc.UserServiceServicer):
        def __init__(self):
            self._store = {}
            self._id = 1

        async def Register(self, request, context):  # type: ignore[override]
            uid = self._id
            self._id += 1
            user = user_pb2.User(
                id=uid,
                username=request.username,
                email=request.email,
                is_active=True,
                is_superuser=False,
            )
            self._store[uid] = user
            return user_pb2.UserReply(user=user)

        async def Login(self, request, context):  # type: ignore[override]
            return user_pb2.LoginReply(
                access_token="fake-access",
                refresh_token="fake-refresh",
                token_type="bearer",
                expires_in=3600,
            )

        async def GetUser(self, request, context):  # type: ignore[override]
            user = self._store.get(int(request.id))
            if not user:
                await context.abort(grpc.StatusCode.NOT_FOUND, "用户不存在")
            return user_pb2.UserReply(user=user)

        async def DeleteUser(self, request, context):  # type: ignore[override]
            self._store.pop(int(request.id), None)
            return empty_pb2.Empty()

    server = grpc.aio.server()
    user_pb2_grpc.add_UserServiceServicer_to_server(FakeUserService(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    target = f"127.0.0.1:{port}"
    try:
        yield target, server
    finally:
        await server.stop(grace=None)


async def test_register_then_get_user(grpc_user_server):
    _skip_if_no_generated()
    import grpc
    from grpc_app.generated.forge.v1 import user_pb2, user_pb2_grpc

    target, _ = grpc_user_server
    async with grpc.aio.insecure_channel(target) as channel:
        stub = user_pb2_grpc.UserServiceStub(channel)

        # Register
        reg = await stub.Register(user_pb2.RegisterRequest(
            username="alice", email="alice@example.com", password="x"
        ))
        assert reg.user.id == 1
        assert reg.user.username == "alice"

        # GetUser
        got = await stub.GetUser(user_pb2.GetUserRequest(id=1))
        assert got.user.id == 1


async def test_exception_mapping_invalid_argument():
    _skip_if_no_generated()
    import grpc
    from grpc_app.generated.forge.v1 import user_pb2, user_pb2_grpc
    from domain.common.exceptions import DomainValidationException
    from grpc_app.interceptors.exceptions import ExceptionMappingInterceptor

    class RaiseOnRegister(user_pb2_grpc.UserServiceServicer):
        async def Register(self, request, context):  # type: ignore[override]
            raise DomainValidationException("参数验证失败", field="username")

    server = grpc.aio.server(interceptors=[ExceptionMappingInterceptor()])
    user_pb2_grpc.add_UserServiceServicer_to_server(RaiseOnRegister(), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    target = f"127.0.0.1:{port}"
    try:
        async with grpc.aio.insecure_channel(target) as channel:
            stub = user_pb2_grpc.UserServiceStub(channel)
            with pytest.raises(grpc.aio.AioRpcError) as ei:
                await stub.Register(user_pb2.RegisterRequest(
                    username="x", email="e@example.com", password="p"
                ))
            assert ei.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    finally:
        await server.stop(grace=None)

