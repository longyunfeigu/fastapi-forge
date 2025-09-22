gRPC usage examples with grpcurl

Prerequisites
- Install grpcurl (https://github.com/fullstorydev/grpcurl)
- Run the gRPC server: `python grpc_main.py` or `docker-compose up -d grpc`

Notes
- These examples use local proto files instead of server reflection. Adjust the `-import-path` to your workspace root.
- For plaintext (no TLS) servers add `-plaintext`.

Describe service (using local proto; server reflection not enabled by default)
```bash
grpcurl -plaintext \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  localhost:50051 describe forge.v1.UserService
```

Health check
```bash
grpcurl -plaintext \
  localhost:50051 grpc.health.v1.Health/Check
```

Register
```bash
grpcurl -plaintext \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  -d '{
    "username": "alice",
    "email": "alice@example.com",
    "password": "P@ssw0rd123",
    "fullName": "Alice",
    "phone": "+8613800138000"
  }' \
  localhost:50051 forge.v1.UserService/Register
```

Login (get access/refresh tokens)
```bash
grpcurl -plaintext \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  -d '{"username":"alice","password":"P@ssw0rd123"}' \
  localhost:50051 forge.v1.UserService/Login
```

GetUser (authorized)
```bash
ACCESS_TOKEN="<paste-access-token>"
grpcurl -plaintext \
  -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  -d '{"id":1}' \
  localhost:50051 forge.v1.UserService/GetUser
```

ListUsers with filter (note: proto3 JSON uses lowerCamelCase; BoolValue wrapper)
```bash
grpcurl -plaintext \
  -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  -d '{"page":1, "pageSize": 20, "isActive": {"value": true}}' \
  localhost:50051 forge.v1.UserService/ListUsers
```

UpdateUser (wrappers for optional fields)
```bash
grpcurl -plaintext \
  -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  -d '{"id":1, "fullName": {"value": "Alice A."}}' \
  localhost:50051 forge.v1.UserService/UpdateUser
```

ChangePassword
```bash
grpcurl -plaintext \
  -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos \
  -proto forge/v1/user.proto \
  -d '{"id":1, "oldPassword":"P@ssw0rd123", "newPassword":"NewP@ssw0rd456"}' \
  localhost:50051 forge.v1.UserService/ChangePassword
```

DeactivateUser / ActivateUser / DeleteUser
```bash
grpcurl -plaintext -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos -proto forge/v1/user.proto -d '{"id":1}' \
  localhost:50051 forge.v1.UserService/DeactivateUser

grpcurl -plaintext -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos -proto forge/v1/user.proto -d '{"id":1}' \
  localhost:50051 forge.v1.UserService/ActivateUser

grpcurl -plaintext -H "authorization: Bearer ${ACCESS_TOKEN}" \
  -import-path grpc_app/protos -proto forge/v1/user.proto -d '{"id":1}' \
  localhost:50051 forge.v1.UserService/DeleteUser
```

Troubleshooting
- If you see "not found: UserService", ensure `scripts/gen_protos.sh` has been run and the server has started with the same proto version.
- For TLS servers, remove `-plaintext` and add `-cacert`/`-cert`/`-key` as needed.
- If you prefer `grpcurl list`, enable server reflection (not enabled by default) or use local proto with `describe` as shown above.

Notes on null vs empty strings
- The User message maps optional string fields that may appear empty when the source is null. If your client needs to distinguish `null` from empty, consider extending the proto using wrapper types or a separate presence flag.
