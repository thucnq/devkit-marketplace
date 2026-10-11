# docs/estimate/items.json

```json
{
  "title": "BÁO GIÁ GIAI ĐOẠN 1 - <TÊN HỆ THỐNG>",
  "subtitle": "<quy mô · ràng buộc chính · số giao diện · hình thức bàn giao>",
  "params": {
    "hourly_rate": 175000,
    "hours_per_day": 8,
    "overhead_pct": 0.30,
    "engineers": 3,
    "working_days_per_month": 22,
    "usd_vnd": 26000,
    "ops_fee_month": 4200000,
    "ops_note": "Vận hành và hướng dẫn 3 năm, sau đó bàn giao đầy đủ kèm tài liệu vận hành",
    "deposit_pct": 0.5,
    "warranty_months": 2,
    "uat_weeks": 2
  },
  "infra": [
    {"name": "On-premise", "one_time": 126000000, "one_time_billed": 7000000, "monthly": 4200000},
    {"name": "Cloud (Render)", "one_time": 5600000, "one_time_billed": 5600000, "monthly": 8320000}
  ],
  "items": [
    {"module": "Nền tảng", "name": "Khởi tạo dự án & hạ tầng", "desc": "Golden path, CI/CD, môi trường staging", "points": 3},
    {"module": "Bán hàng", "name": "Quản lý đơn hàng", "desc": "AC-ORDER-01..12", "points": 6.5, "optional": false},
    {"module": "Báo cáo", "name": "Xuất Excel", "desc": "AC-REPORT-01..04", "points": 2, "optional": true},
    {"module": "Tích hợp", "name": "Import MISA", "desc": "Định dạng file chưa rõ", "points": 4, "open": true, "question": "Khách cung cấp file mẫu MISA cho từng công ty?"}
  ],
  "questions": [
    {"q": "Câu hỏi thêm không gắn với hạng mục", "why": "…", "default": "…"}
  ]
}
```

- `one_time` = tổng chi phí một lần của phương án (dùng cho TCO); `one_time_billed` = phần thu qua báo giá vào ngày ký.
- TCO N năm = `one_time + monthly × 12 × N`.
- Thanh toán: ngày ký = `deposit_pct × build bắt buộc + one_time_billed`; nghiệm thu cuối = phần build còn lại.
- Ngày công = điểm × (1 + overhead); thời gian (tháng) = ngày công / số kỹ sư / ngày làm việc mỗi tháng.
