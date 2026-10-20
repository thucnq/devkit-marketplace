# 0001 - Dùng golden path cho dự án freelance tải thấp

- Trạng thái: Đã chấp nhận
- Ngày: (ngày khởi tạo dự án)

## Bối cảnh
Dự án freelance thường có tải thấp (≤ 50 người dùng đồng thời), ngân sách hạ tầng gần 0 và cần bàn giao đầy đủ. Bảo mật, audit và dữ liệu cá nhân là bắt buộc.

## Quyết định
- Monorepo Maven (Java 21, Spring Boot 3.5) + React/Vite; app mobile bằng Capacitor từ cùng mã web.
- Một PostgreSQL duy nhất; cách ly tenant bằng Row-Level Security; ứng dụng kết nối bằng role `app_rw` không phải owner.
- Xác thực tự quản lý: JWT HS256 15 phút + refresh token xoay vòng trong cookie HttpOnly/SameSite=Strict; Google SSO chỉ cho người dùng đã được mời.
- Audit trong Postgres, phân vùng theo tháng, giữ 3 tháng (cấu hình được).
- Triển khai Docker Compose + Caddy trên một VM; không registry, không Kubernetes, không Kafka/Redis.

## Hệ quả
- Chi phí vận hành ~0, một người vận hành được.
- Mở rộng ngang cần thêm: rate-limit dùng chung (hiện ở bộ nhớ), lưu file sang object storage. Khi BRD cho thấy cần, viết ADR mới.
- App mobile native gọi API khác origin: cookie SameSite=Strict không được gửi. Khi dự án cần app mobile, viết ADR chọn cách lưu refresh token an toàn trên thiết bị (Secure Storage) và gửi qua body.

## Phương án đã loại
- Keycloak: đầy đủ nhưng tốn ~512 MB RAM và thêm một hệ thống phải vận hành.
- Schema-per-tenant: migration phức tạp hơn nhiều so với RLS ở quy mô này.
