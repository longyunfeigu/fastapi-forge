#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
proto_dir="$root_dir/grpc_app/protos"
out_dir="$root_dir/grpc_app/generated"

mkdir -p "$out_dir"

# Prefer python3 explicitly; fallback to python
PY_BIN="python3"
command -v python3 >/dev/null 2>&1 || PY_BIN="python"

"$PY_BIN" -m grpc_tools.protoc \
  -I"$proto_dir" \
  --python_out="$out_dir" \
  --grpc_python_out="$out_dir" \
  $(find "$proto_dir" -name "*.proto" -print)

echo "Protos generated to $out_dir"
