# 刷新令牌轮转（Refresh Token Rotation）

本文档详细说明 FastAPI Forge 项目中实现的刷新令牌轮转机制，这是一个重要的安全增强功能。

---

## 什么是刷新令牌轮转？

刷新令牌轮转（Refresh Token Rotation）是一种 OAuth 2.0 安全最佳实践，用于防止刷新令牌被盗用和重放攻击。

### 传统方式的问题

在传统的 JWT 实现中：
- 刷新令牌长期有效（如 7-30 天）
- 同一个刷新令牌可以多次使用
- 如果刷新令牌被盗，攻击者可以持续获取新的访问令牌
- 无法检测令牌是否被盗用

### 轮转方式的优势

✅ **一次性使用**：每个刷新令牌只能使用一次
✅ **自动失效**：使用后立即失效，生成新令牌
✅ **检测重用**：如果检测到已使用的令牌再次被使用，立即撤销整个令牌家族
✅ **追踪链路**：记录令牌的父子关系，形成完整的轮转链
✅ **设备追踪**：记录设备信息和 IP 地址

---

## 工作原理

### 登录流程

```
1. 用户登录
   ↓
2. 生成令牌对：
   - Access Token (短期，15分钟)
   - Refresh Token (长期，7天)
   ↓
3. 将 Refresh Token 存储到数据库：
   - JTI (令牌ID)
   - Family ID (家族ID)
   - Token Hash (SHA-256)
   - Device Info
   - IP Address
```

### 刷新流程（轮转）

```
1. 客户端使用 Refresh Token 请求新令牌
   ↓
2. 服务端验证：
   - 签名有效？
   - 令牌未过期？
   - 令牌存在于数据库？
   - 令牌未被撤销？
   - 令牌未被使用？ ⚠️ 关键检查
   ↓
3. 如果所有检查通过：
   - 标记旧令牌为"已使用"
   - 生成新的 Access Token
   - 生成新的 Refresh Token（同一 Family ID）
   - 记录 Parent JTI（追踪链路）
   ↓
4. 返回新令牌对
```

### 重用检测（安全机制）

```
1. 客户端使用已使用的 Refresh Token
   ↓
2. 服务端检测到：token.is_used == True
   ↓
3. 触发安全响应：
   - 撤销整个令牌家族（所有相关令牌）
   - 记录安全事件日志
   - 返回 401 错误
   ↓
4. 用户需要重新登录
```

---

## 数据库结构

### `refresh_tokens` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer | 主键 |
| `jti` | String(64) | JWT Token ID（唯一） |
| `user_id` | Integer | 用户ID（外键） |
| `family_id` | String(64) | 令牌家族ID |
| `parent_jti` | String(64) | 父令牌JTI（追踪链路） |
| `token_hash` | String(128) | 令牌SHA-256哈希 |
| `is_revoked` | Boolean | 是否已撤销 |
| `is_used` | Boolean | 是否已使用 |
| `device_info` | Text | 设备信息（User-Agent） |
| `ip_address` | String(45) | IP地址 |
| `created_at` | DateTime | 创建时间 |
| `expires_at` | DateTime | 过期时间 |
| `used_at` | DateTime | 使用时间 |
| `revoked_at` | DateTime | 撤销时间 |
| `revoke_reason` | String(200) | 撤销原因 |

### 索引优化

```sql
-- 主要查询索引
CREATE INDEX ix_refresh_tokens_jti ON refresh_tokens(jti);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX ix_refresh_tokens_family_id ON refresh_tokens(family_id);

-- 复合索引
CREATE INDEX ix_refresh_tokens_user_active ON refresh_tokens(user_id, is_revoked, is_used);
CREATE INDEX ix_refresh_tokens_family_active ON refresh_tokens(family_id, is_revoked);
CREATE INDEX ix_refresh_tokens_expires ON refresh_tokens(expires_at, is_revoked);
```

---

## API 使用

### 1. 登录

```bash
curl -X POST http://localhost:8000/api/v1/users/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=SecurePass123"
```

响应：
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 900
}
```

### 2. 刷新令牌（轮转）

```bash
curl -X POST http://localhost:8000/api/v1/users/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }'
```

响应：
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",  // 新的访问令牌
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",  // 新的刷新令牌（旧的已失效）
  "token_type": "bearer",
  "expires_in": 900
}
```

⚠️ **重要**：旧的 `refresh_token` 已失效，必须使用新的。

### 3. 查看活跃会话

```bash
curl -X GET http://localhost:8000/api/v1/users/me/sessions \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

响应：
```json
{
  "code": 0,
  "message": "找到 2 个活跃会话",
  "data": [
    {
      "jti": "a1b2c3d4-...",
      "family_id": "f1e2d3c4-...",
      "created_at": "2025-10-07T12:00:00Z",
      "expires_at": "2025-10-14T12:00:00Z",
      "device_info": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
      "ip_address": "192.168.1.100"
    },
    {
      "jti": "e5f6g7h8-...",
      "family_id": "k9l0m1n2-...",
      "created_at": "2025-10-07T10:00:00Z",
      "expires_at": "2025-10-14T10:00:00Z",
      "device_info": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0...)...",
      "ip_address": "192.168.1.101"
    }
  ]
}
```

### 4. 登出所有设备

```bash
curl -X POST http://localhost:8000/api/v1/users/me/logout-all \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

响应：
```json
{
  "code": 0,
  "message": "已撤销 2 个刷新令牌",
  "data": {
    "revoked_count": 2
  }
}
```

---

## 安全特性

### 1. 令牌重用检测

**场景**：攻击者窃取了刷新令牌

```
时间线：
T1: 用户正常刷新令牌 → Token A 失效，获得 Token B
T2: 攻击者使用 Token A（已失效）→ 检测到重用
T3: 系统撤销整个家族（Token B 也失效）
T4: 用户和攻击者都需要重新登录
```

这确保了即使攻击者窃取了令牌，也能被快速检测并阻止。

### 2. 令牌家族（Token Family）

同一次登录产生的所有令牌共享同一个 `family_id`：

```
Login (Family: F1)
  ├─ Token A (JTI: a1)
  │   └─ Refresh → Token B (JTI: b1, Parent: a1)
  │       └─ Refresh → Token C (JTI: c1, Parent: b1)
  │           └─ Refresh → Token D (JTI: d1, Parent: c1)
  └─ 如果检测到 Token A/B/C 重用，撤销 A/B/C/D 全部
```

### 3. 令牌哈希存储

数据库中存储令牌的 SHA-256 哈希，而非明文：

```python
token_hash = hashlib.sha256(token.encode()).hexdigest()
```

即使数据库泄露，攻击者也无法直接使用令牌。

### 4. 设备和IP追踪

记录每个令牌的：
- User-Agent（设备类型、浏览器）
- IP 地址

用于：
- 安全审计
- 异常登录检测
- 用户查看登录设备列表

---

## 配置

在 `.env` 或 `core/config.py` 中配置：

```bash
# 访问令牌过期时间（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES=15

# 刷新令牌过期时间（天）
REFRESH_TOKEN_EXPIRE_DAYS=7

# JWT 密钥（必须设置）
SECRET_KEY=your-secret-key-here

# JWT 算法
ALGORITHM=HS256
```

---

## 最佳实践

### 客户端实现

```typescript
// 存储令牌
function saveTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem('access_token', accessToken);
  localStorage.setItem('refresh_token', refreshToken);
}

// API请求拦截器
axios.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;

    // 如果 401 且未重试过
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // 使用刷新令牌获取新令牌
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post('/api/v1/users/refresh', {
          refresh_token: refreshToken
        });

        const { access_token, refresh_token } = response.data;

        // 保存新令牌（旧的已失效）
        saveTokens(access_token, refresh_token);

        // 重试原请求
        originalRequest.headers['Authorization'] = `Bearer ${access_token}`;
        return axios(originalRequest);
      } catch (refreshError) {
        // 刷新失败，跳转到登录页
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

### 并发请求处理

⚠️ **重要**：避免多个并发请求同时刷新令牌

```typescript
let refreshTokenPromise: Promise<any> | null = null;

async function getValidToken() {
  const accessToken = localStorage.getItem('access_token');

  // 检查令牌是否即将过期（例如，剩余时间 < 1分钟）
  if (isTokenExpiringSoon(accessToken)) {
    // 如果已经有刷新请求在进行中，等待它
    if (!refreshTokenPromise) {
      refreshTokenPromise = refreshAccessToken().finally(() => {
        refreshTokenPromise = null;
      });
    }
    await refreshTokenPromise;
  }

  return localStorage.getItem('access_token');
}
```

---

## 维护与监控

### 定期清理过期令牌

建议设置定时任务清理已过期的令牌：

```python
from application.services.token_service import TokenService

# 清理 30 天前过期的令牌
token_service = TokenService(uow_factory)
count = await token_service.cleanup_expired_tokens(days_before=30)
print(f"Cleaned {count} expired tokens")
```

使用 Celery 定时任务：

```python
# infrastructure/tasks/tasks/cleanup.py
from celery import shared_task
from application.services.token_service import TokenService
from infrastructure.unit_of_work import SQLAlchemyUnitOfWork

@shared_task(name="cleanup.expired_tokens")
def cleanup_expired_tokens():
    """每天清理过期的刷新令牌"""
    token_service = TokenService(SQLAlchemyUnitOfWork)
    count = asyncio.run(token_service.cleanup_expired_tokens(days_before=30))
    return {"cleaned": count}
```

### 监控指标

建议监控以下指标：

1. **令牌重用检测次数**：异常峰值可能表示攻击
2. **令牌家族撤销次数**：安全事件指标
3. **活跃令牌数量**：资源使用情况
4. **平均令牌生命周期**：用户行为分析

---

## 故障排查

### 问题：用户频繁需要重新登录

**原因**：
- 刷新令牌过期时间太短
- 客户端未正确存储新令牌
- 并发刷新导致令牌被撤销

**解决**：
1. 检查 `REFRESH_TOKEN_EXPIRE_DAYS` 配置
2. 检查客户端代码是否更新令牌
3. 实现并发刷新保护

### 问题：提示"检测到令牌重用"

**原因**：
- 客户端存储了多个刷新令牌副本
- 多个设备/标签页同时刷新
- 真实的安全攻击

**解决**：
1. 检查客户端是否正确管理令牌
2. 实现单例刷新机制
3. 检查安全日志确认是否为攻击

### 问题：数据库中令牌记录过多

**原因**：
- 未配置定期清理任务
- 用户频繁登录登出

**解决**：
1. 设置定时清理任务
2. 考虑减少刷新令牌过期时间
3. 数据库分区或归档旧数据

---

## 安全建议

1. **使用 HTTPS**：所有令牌传输必须加密
2. **安全存储**：客户端使用 `httpOnly` Cookie 或安全存储
3. **短期访问令牌**：15分钟或更短
4. **合理的刷新令牌期限**：7-30天
5. **监控异常**：记录并监控令牌重用事件
6. **定期轮换密钥**：考虑定期更换 `SECRET_KEY`
7. **多因素认证**：对敏感操作启用 MFA
8. **IP白名单**：敏感账户可限制 IP 范围

---

## 参考资源

- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [RFC 6749 - The OAuth 2.0 Authorization Framework](https://tools.ietf.org/html/rfc6749)
- [OWASP JWT Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
