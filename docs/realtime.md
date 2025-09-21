# Realtime WebSocket Guide

本指南介绍本项目的实时通讯（WebSocket）能力：架构设计、使用方式、消息协议、扩容与配置，以及常见的扩展点（ACL、限流、背压）。

## 架构概览
- 路由：`/api/v1/ws`（FastAPI WebSocket）
- 分层职责：
  - API（`api/routes/ws.py`）：握手/鉴权、解析 JSON、调用应用服务、处理 ping/pong
  - Application（`application/services/realtime_service.py`）：用例编排（join/leave/send）、ACL 检查、消费跨实例事件并分发至连接
  - Port（`application/ports/realtime.py`）：`RealtimeBrokerPort` + `Envelope` DTO（统一消息壳）
  - Infrastructure：
    - 连接管理：`infrastructure/realtime/connection_manager.py`（本进程内房间/连接表、广播）
    - 广播实现（Broker）：
      - 单机：`infrastructure/realtime/brokers/inmemory.py`
      - 多实例：`infrastructure/realtime/brokers/redis.py`（Redis Pub/Sub）
- 装配：`main.py` lifespan 中初始化 broker + connection manager + service，并注册订阅回调。

## 连接与鉴权
- 建立连接：
  - `ws://<host>/api/v1/ws?token=<ACCESS_TOKEN>`
  - 或使用 Header：`Authorization: Bearer <ACCESS_TOKEN>`
- 鉴权逻辑：沿用 `UserApplicationService.verify_token`；无效/过期将拒绝（1008）。

## 消息协议（JSON Envelope）
服务端与客户端统一用 Envelope 壳：
```
{
  "type": "message|join|leave|ping|pong|error|welcome|system",
  "room": "r1" | null,
  "data": { ... },
  "ts": "2025-09-20T10:10:10Z",
  "sender_id": 123
}
```

- 客户端 → 服务端
  - 加入房间：`{"type":"join","room":"r1"}`
  - 离开房间：`{"type":"leave","room":"r1"}`
  - 发送消息：`{"type":"message","room":"r1","text":"hello"}` 或 `{"type":"message","room":"r1","data":{"text":"hello"}}`
  - 心跳：`{"type":"ping"}`
- 服务端 → 客户端
  - 欢迎：`{"type":"welcome","data":{"user_id":<id>}}`
  - 消息广播：`{"type":"message","room":"r1","data":{...},"sender_id":<id>}`
  - 心跳应答：`{"type":"pong"}`
  - 错误：`{"type":"error","data":{"message":"forbidden|room required|unknown type"}}`

## 房间 ACL（访问控制）
默认策略（可扩展）：
- `public:*`：任何用户可加入/发送
- `private:<user_id>`：仅 `<user_id>` 本人或超级管理员可加入/发送
- 其它：默认允许

实现位置：`RealtimeService._ensure_can_join/_ensure_can_send`。若不符合策略，则抛出 `PermissionError`，API 层返回 `error` envelope。

你可以按需替换为更复杂的 ACL（如团队/角色/白名单），建议仍放在 `RealtimeService` 中，保持 API/Infra 的 SRP。

## 背压与发送队列上限
为避免慢连接拖垮事件循环，连接管理器为每个 WebSocket 维护一个发送队列：
- 队列长度：`REALTIME_WS_SEND_QUEUE_MAX`（默认 100）
- 溢出策略：`REALTIME_WS_SEND_OVERFLOW_POLICY`（默认 `drop_oldest`）
  - `drop_oldest`：丢弃最早消息，保留最新
  - `drop_new`：丢弃新来的消息
  - `disconnect`：断开该连接（1013）

实现位置：`infrastructure/realtime/connection_manager.py`。

## 多实例部署
- 设置 `REDIS__URL` 后，系统自动使用 Redis Pub/Sub 广播（频道 `rt:room:{room}`），跨实例同步房间消息。
- 未配置 Redis 时使用内存版（仅单实例）。

## 配置汇总（.env）
```
# WebSocket 背压队列
REALTIME_WS_SEND_QUEUE_MAX=100
REALTIME_WS_SEND_OVERFLOW_POLICY=drop_oldest  # drop_oldest | drop_new | disconnect

# Redis（用于跨实例广播）
REDIS__URL=redis://localhost:6379/0
```

## 客户端示例（浏览器）
```
const ws = new WebSocket("ws://localhost:8000/api/v1/ws?token=ACCESS_TOKEN");
ws.onopen = () => {
  ws.send(JSON.stringify({type:"join", room:"public:lobby"}));
  ws.send(JSON.stringify({type:"message", room:"public:lobby", text:"hello"}));
};
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  console.log("event", msg.type, msg);
};
```

## 扩展示例
- 私聊：发送 `{"type":"direct","data":{"to":123,"text":"..."}}`，在 `RealtimeService` 新增 `send_direct` 并调用 `connections.broadcast_user(to, env)`。
- 服务器通知：在应用层任意用例中 `await broker.publish(room, Envelope(type="system", room, data=...))`。
- Kafka 集成：实现 `RealtimeBrokerPort` 的 Kafka 适配（topic: `rt.room.<room>.v1`），在 `main.py` 装配选择。

## 源码索引
- API：api/routes/ws.py:1
- Application：application/services/realtime_service.py:1
- Port & DTO：application/ports/realtime.py:1
- Connection Manager：infrastructure/realtime/connection_manager.py:1
- Brokers：infrastructure/realtime/brokers/inmemory.py:1, .../redis.py:1
- 装配：main.py:34

