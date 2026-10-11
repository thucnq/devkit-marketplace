---
name: vn-data-protection
description: Vietnam personal data protection rules (Luật Bảo vệ dữ liệu cá nhân 2025 + Nghị định 356/2025/NĐ-CP) translated into engineering requirements. Use when a feature collects, stores, or processes personal data — especially biometric, health, ID card, location, or children's data.
user-invocable: false
---

# Bảo vệ dữ liệu cá nhân — yêu cầu kỹ thuật

> Đây là bản tóm tắt kỹ thuật để thiết kế, không phải tư vấn pháp lý. Với dự án xử lý dữ liệu nhạy cảm, khuyên khách hàng tham khảo luật sư trước khi go-live. Luôn kiểm tra văn bản hiện hành tại thuvienphapluat.vn trước khi chốt thiết kế.

## 1. Phân loại (ghi vào BRD mục 5.2)
- **Cơ bản**: họ tên, ngày sinh, giới tính, số điện thoại, email, địa chỉ, quốc tịch, ảnh chân dung thông thường, tài khoản mạng xã hội.
- **Nhạy cảm** (luôn xem là nhạy cảm khi thiết kế): **dữ liệu sinh trắc học (vân tay, khuôn mặt, mống mắt, giọng nói)**, sức khỏe, di truyền, tôn giáo, quan điểm chính trị, đời sống tình dục/xu hướng tính dục, tiền án tiền sự, vị trí chính xác, số CCCD/hộ chiếu kèm ảnh, thông tin tài khoản ngân hàng/tín dụng, dữ liệu của **trẻ em**.

## 2. Hệ quả thiết kế
| Yêu cầu | Cơ bản | Nhạy cảm |
|---|---|---|
| Đồng ý của chủ thể | Rõ ràng, chủ động (checkbox không tích sẵn), ghi mục đích | Đồng ý **riêng** cho từng mục đích, nêu rõ là dữ liệu nhạy cảm; trẻ em: đồng ý của cha mẹ/người giám hộ (và của trẻ nếu đủ tuổi theo luật) |
| Lưu bằng chứng đồng ý | Bảng `consent` (subject, purpose, version văn bản, thời điểm, IP, kênh) — append-only | như bên trái + audit mọi lượt đọc |
| Mã hóa | TLS khi truyền | TLS + **mã hóa khi lưu** (`PiiEncryptedConverter`, `EncryptedFileStore`) |
| Tối thiểu hóa | Chỉ thu trường cần cho mục đích | Xóa dữ liệu gốc (ví dụ ảnh vân tay) ngay khi đã trích xuất xong, trừ khi mục đích yêu cầu giữ |
| Quyền chủ thể | API/chức năng: xem, sửa, xuất, **rút lại đồng ý**, **xóa** | như bên trái, thời hạn xử lý ngắn |
| Hồ sơ đánh giá tác động | Khuyến nghị | **Bắt buộc lập và lưu** — tạo `docs/compliance/dpia.md` |
| Chuyển dữ liệu ra nước ngoài | Lập hồ sơ đánh giá | như bên trái — lưu ý: gọi API AI/cloud ở nước ngoài để xử lý ảnh cũng là chuyển dữ liệu ra nước ngoài |
| Sự cố | Quy trình thông báo trong runbook | như bên trái |

## 3. Checklist bắt buộc cho tính năng có dữ liệu nhạy cảm
- [ ] AC cho luồng đồng ý, rút lại đồng ý, xóa dữ liệu (tính cả bản sao lưu: ghi rõ thời hạn hết hạn backup)
- [ ] Cột/ file mã hóa; khóa mã hóa ở biến môi trường, có quy trình xoay khóa trong runbook
- [ ] Audit mọi lượt đọc
- [ ] Không gửi dữ liệu thô sang dịch vụ bên thứ ba (AI, OCR, analytics) nếu chưa có trong văn bản đồng ý và hồ sơ chuyển ra nước ngoài
- [ ] `docs/compliance/dpia.md`: loại dữ liệu, mục đích, cơ sở pháp lý, thời gian lưu, biện pháp bảo vệ, rủi ro còn lại
- [ ] Chính sách quyền riêng tư (tiếng Việt) hiển thị trước khi thu thập
- [ ] Nếu kết quả xử lý có thể ảnh hưởng đến quyết định về con người (tuyển dụng, học tập…): hiển thị rõ giới hạn và cơ sở khoa học của kết quả; không trình bày suy luận như sự thật
