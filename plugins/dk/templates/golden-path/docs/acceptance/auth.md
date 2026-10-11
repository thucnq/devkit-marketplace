# Tiêu chí nghiệm thu — Đăng nhập (AUTH)

> Có sẵn trong golden path. Giữ nguyên file này trừ khi dự án đổi cơ chế đăng nhập.

### AC-AUTH-01: Đăng nhập thành công
- **Cho** người dùng đang hoạt động với email và mật khẩu đúng
- **Khi** gửi `POST /api/auth/login`
- **Thì** nhận 200 kèm access token (15 phút) và cookie `rt` HttpOnly, SameSite=Strict, Path=/api/auth; ghi audit `LOGIN`
- Ưu tiên: Bắt buộc

### AC-AUTH-02: Sai mật khẩu
- **Cho** email tồn tại hoặc không tồn tại
- **Khi** đăng nhập với mật khẩu sai
- **Thì** nhận 401 với cùng một thông báo (không lộ email có tồn tại hay không); ghi audit `LOGIN_FAILED`
- Ưu tiên: Bắt buộc

### AC-AUTH-03: Chống dò mật khẩu
- **Cho** 5 lần đăng nhập sai trong 15 phút từ cùng IP và email
- **Khi** đăng nhập lần thứ 6, kể cả đúng mật khẩu
- **Thì** nhận 429
- Ưu tiên: Bắt buộc

### AC-AUTH-04: Làm mới phiên
- **Cho** cookie refresh hợp lệ
- **Khi** gửi `POST /api/auth/refresh`
- **Thì** nhận access token mới và cookie refresh mới (token cũ bị thu hồi)
- Ưu tiên: Bắt buộc

### AC-AUTH-05: Phát hiện dùng lại refresh token
- **Cho** refresh token đã bị xoay vòng
- **Khi** dùng lại token cũ
- **Thì** nhận 401 và toàn bộ phiên (kể cả token mới) bị thu hồi
- Ưu tiên: Bắt buộc

### AC-AUTH-06: Đăng xuất
- **Cho** người dùng đang đăng nhập
- **Khi** gửi `POST /api/auth/logout`
- **Thì** nhận 204, cookie bị xóa, refresh token không dùng lại được
- Ưu tiên: Bắt buộc
