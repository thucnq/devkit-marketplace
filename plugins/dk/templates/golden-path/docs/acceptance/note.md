# Tiêu chí nghiệm thu — Ghi chú (NOTE)

> Tính năng mẫu để minh họa cấu trúc. Xóa cùng package `feature/note` và `V2__note.sql` khi bắt đầu dự án thật
> (nhớ tạo migration mới `drop table note` nếu đã chạy trên môi trường nào đó).

### AC-NOTE-01: Tạo ghi chú
- **Cho** người dùng vai trò USER đã đăng nhập
- **Khi** gửi `POST /api/notes` với tiêu đề hợp lệ
- **Thì** nhận 201, chủ sở hữu là người tạo, version = 0; ghi audit `NOTE_CREATE`
- Ưu tiên: Bắt buộc

### AC-NOTE-02: Danh sách có phân trang
- **Cho** tenant A có 3 ghi chú, tenant B có 1 ghi chú
- **Khi** người dùng tenant A gọi `GET /api/notes?size=2`
- **Thì** nhận 2 ghi chú, total = 3; size tối đa 100 dù yêu cầu lớn hơn
- Ưu tiên: Bắt buộc

### AC-NOTE-03: Chống ghi đè đồng thời
- **Cho** ghi chú đã được người khác cập nhật (version tăng)
- **Khi** gửi `PUT` với version cũ
- **Thì** nhận 409, dữ liệu không đổi
- Ưu tiên: Bắt buộc

### AC-NOTE-04: Quyền xóa
- **Cho** ghi chú của Alice
- **Khi** Bob (USER) xóa → 403; Alice xóa → 204 và ghi audit `NOTE_DELETE`; ADMIN xóa ghi chú của người khác → 204
- **Thì** như trên
- Ưu tiên: Bắt buộc

### AC-NOTE-05: Bắt buộc đăng nhập
- **Cho** không có access token
- **Khi** gọi bất kỳ API ghi chú nào
- **Thì** nhận 401
- Ưu tiên: Bắt buộc
