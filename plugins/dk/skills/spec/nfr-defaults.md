# NFR mặc định (dự án freelance tải thấp, hạ tầng ~$0)

Mỗi dòng có cách kiểm chứng tự động — NFR không kiểm chứng được thì không ghi vào BRD.

| Nhóm | Yêu cầu mặc định | Kiểm chứng bằng |
|---|---|---|
| Hiệu năng | p95 < 300 ms cho API đọc, < 800 ms cho API ghi, ở 20 người dùng đồng thời, trên máy 1 vCPU / 1 GB | k6 smoke `deploy/k6/smoke.js` (thresholds) trong `/dk:ship` |
| Tải | ≤ 50 người dùng đồng thời, ≤ 100k bản ghi/bảng/năm | Không cần sharding, cache phân tán, hay message broker |
| Khả dụng | Best-effort 99%; tự khởi động lại container (`restart: unless-stopped`); healthcheck | `docker compose ps`, Actuator `/actuator/health` |
| Sao lưu | `pg_dump` hằng ngày, giữ 7 bản, lưu ngoài máy chủ | `deploy/backup.sh` + kiểm tra restore mỗi lần ship |
| Bảo mật | OWASP ASVS L1; JWT access 15 phút + refresh 7 ngày xoay vòng; mật khẩu BCrypt; rate-limit đăng nhập; HTTPS bắt buộc | Semgrep, gitleaks, OWASP dependency-check, test `AC-*-VALIDATION` |
| Phân quyền | RBAC theo vai trò; cách ly tenant bằng Postgres RLS | Test `AC-*-TENANT` cho mọi tính năng |
| Audit | Ghi mọi thao tác thay đổi dữ liệu nghiệp vụ và mọi lượt xem dữ liệu nhạy cảm; lưu 3 tháng (cấu hình `app.audit.retention-months`) | Test audit trong AC; job dọn partition |
| Dữ liệu cá nhân | Mask trong log; mã hóa cột với dữ liệu nhạy cảm; có chức năng xuất/xóa dữ liệu theo yêu cầu chủ thể | ArchUnit + test `PiiMaskingTest` |
| Khả năng bảo trì | Kiến trúc package-by-feature; quy tắc lớp kiểm tra bằng ArchUnit; độ phủ test dòng ≥ 70% ở tầng service | `./mvnw verify` (JaCoCo) |
| Quan sát | Log JSON có `traceId`, `tenantId` (không có PII); Actuator health/metrics | Kiểm tra trong `/dk:ship` |
| Tương thích | Trình duyệt Chrome/Edge/Safari 2 phiên bản gần nhất; responsive ≥ 360 px; app mobile qua Capacitor khi cần | Playwright smoke (tùy chọn) |
