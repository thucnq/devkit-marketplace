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
    "uat_weeks": 2,
    "start_date": "2026-10-19",
    "team": ["Thuc", "Nam", "Hà"],
    "holidays": ["2026-02-14..2026-02-22", "2026-04-27", "2026-09-01"]
  },
  "infra": [
    {"name": "On-premise", "one_time": 126000000, "one_time_billed": 7000000, "monthly": 4200000},
    {"name": "Cloud (Render)", "one_time": 5600000, "one_time_billed": 5600000, "monthly": 8320000}
  ],
  "items": [
    {"id": "NEN", "module": "Nền tảng", "name": "Khởi tạo dự án & hạ tầng", "desc": "Golden path, CI/CD, môi trường staging", "points": 3, "risk": "LOW"},
    {"id": "ORDER", "module": "Bán hàng", "name": "Quản lý đơn hàng", "desc": "AC-ORDER-01..12", "points": 6.5, "optional": false,
     "deps": ["NEN"], "ac": ["AC-ORDER"], "risk": "MEDIUM"},
    {"id": "REPORT", "module": "Báo cáo", "name": "Xuất Excel", "desc": "AC-REPORT-01..04", "points": 2, "optional": true, "deps": ["ORDER"], "ac": ["AC-REPORT"]},
    {"id": "MISA", "module": "Tích hợp", "name": "Import MISA", "desc": "Định dạng file chưa rõ", "points": 12, "crew": 2, "deps": ["NEN"], "ac": ["AC-MISA"],
     "risk": "HIGH", "open": true, "question": "Khách cung cấp file mẫu MISA cho từng công ty?"},
    {"id": "UAT", "module": "Kiểm thử", "name": "Kiểm thử nghiệm thu & sửa lỗi", "points": 3, "deps": ["*"]}
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

## Trường lập lịch (dùng bởi `/dk:plan`, không ảnh hưởng báo giá)
| Trường | Ý nghĩa |
|---|---|
| `id` | Mã tính năng trong `docs/scope.md`, **không đổi về sau** (tiến độ khớp theo id). Thiếu thì tự đặt `H01`, `H02`… theo thứ tự |
| `deps` | Danh sách `id` phải xong trước. `["*"]` = sau mọi hạng mục đứng trước nó |
| `ac` | Tiền tố AC của tính năng (`["AC-ORDER"]`) hoặc AC cụ thể. Thiếu thì lấy các `AC-XXX` trong `desc` |
| `risk` | `LOW` · `MEDIUM` (mặc định) · `HIGH` - tô màu trên Gantt, `/dk:review` soát kỹ hơn với HIGH |
| `crew` | Số kỹ sư làm song song một hạng mục (mặc định 1) |
| `owner` | Người làm dự kiến (khớp tên trong `params.team`) |
| `params.start_date` | Ngày bắt đầu; mặc định thứ Hai tuần sau |
| `params.team` | Tên kỹ sư; thiếu thì dùng "Kỹ sư 1..N" theo `engineers` |
| `params.hours_per_week` | (0.7.0) Số giờ/tuần mỗi người thực sự dành cho dự án (dự án cá nhân làm ngoài giờ). Thiếu = toàn thời gian (40). Thời lượng mỗi hạng mục × 40 / giờ |
| `params.no_quote` | (0.7.0) `true` khi dự án không báo giá (`/dk:estimate --no-quote`): `gen-quote.py` không chạy, không có các mục bàn giao cho khách |
| `params.holidays` | Ngày nghỉ (`YYYY-MM-DD` hoặc `từ..đến`) **thay** cho danh sách âm lịch mặc định; 1/1, 30/4, 1/5, 2/9 luôn được tính |
| `params.plan_optional` | `true` để đưa hạng mục tùy chọn vào lịch |

- Thời lượng (ngày làm việc) = điểm × (1 + overhead) / crew, làm tròn lên - cùng công thức ngày công với báo giá.
- UAT = `uat_weeks` × 5 ngày làm việc sau hạng mục cuối.
