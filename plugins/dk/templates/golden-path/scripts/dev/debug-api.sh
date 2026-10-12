#!/usr/bin/env bash
# Chạy API ở chế độ debug trong WSL/Linux; IntelliJ (Windows) gắn vào bằng cấu hình "Attach API :5005".
#   bash scripts/dev/debug-api.sh            chạy, không chờ debugger
#   SUSPEND=y bash scripts/dev/debug-api.sh  dừng ở main cho tới khi debugger gắn vào (debug lỗi lúc khởi động)
#   PORT=5006 bash scripts/dev/debug-api.sh  đổi cổng debug
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
docker compose -f deploy/compose.dev.yml up -d db >/dev/null
# address=*:PORT để Windows gắn được qua localhost forwarding của WSL2 (chỉ dùng ở máy dev, không dùng trên server)
JDWP="-agentlib:jdwp=transport=dt_socket,server=y,suspend=${SUSPEND:-n},address=*:${PORT:-5005}"
MVN=./mvnw; [ -x "$MVN" ] || MVN=mvn
exec "$MVN" -q -pl backend spring-boot:run \
  -Dspring-boot.run.profiles=dev \
  -Dspring-boot.run.jvmArguments="$JDWP"
