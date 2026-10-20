# Runbook vận hành - goldenpath

## Cấu hình
Mọi biến môi trường được liệt kê trong `deploy/.env.example`. File thật nằm ở `deploy/envs/<môi-trường>.env` (không commit) và được chép thành `.env` trên máy chủ.

| Biến | Ý nghĩa |
|---|---|
| `DB_OWNER_*` | Tài khoản owner của database - chỉ Flyway dùng |
| `DB_APP_PASSWORD` | Mật khẩu role `app_rw` mà ứng dụng dùng (chịu RLS) |
| `APP_JWT_SECRET` | Khóa ký JWT (`openssl rand -base64 48`). Đổi khóa = mọi người phải đăng nhập lại |
| `APP_PII_KEY`, `APP_PII_HASH_KEY` | Khóa mã hóa dữ liệu cá nhân (`openssl rand -base64 32`). **Mất khóa = mất dữ liệu đã mã hóa.** Lưu bản sao ở nơi an toàn ngoài máy chủ |
| `APP_AUDIT_RETENTION_MONTHS` | Số tháng giữ audit (mặc định 3) |

Mỗi dự án dùng một PostgreSQL riêng (role `app_rw` là role cấp cluster).

## Triển khai
- Non-prod: `/dk:ship staging` hoặc `deploy.sh staging` (từ plugin dk).
- Production: người thực hiện chạy cùng các bước trong `deploy.sh` với file env production; kiểm tra `/api/actuator/health` sau khi lên.
- Cài cron sao lưu trên máy chủ: `0 2 * * * cd /opt/<app> && ./backup.sh >> backups/backup.log 2>&1`

## Vận hành
- Xem log: `docker compose logs -f --tail=200 api`
- Khởi động lại: `docker compose restart api`
- Kiểm tra sao lưu phục hồi được: `./restore-check.sh`

## Sự cố thường gặp
| Triệu chứng | Nguyên nhân thường gặp | Xử lý |
|---|---|---|
| API không khởi động, log báo thiếu `app.security.jwt-secret` | Thiếu biến môi trường | Bổ sung trong `.env`, `docker compose up -d` |
| Mọi API trả danh sách rỗng | Ứng dụng kết nối bằng owner thay vì `app_rw`, hoặc tenant không có trong token | Kiểm tra `DB_APP_USER`, token có claim `tid` |
| Không lấy được chứng chỉ HTTPS | DNS chưa trỏ về máy chủ hoặc cổng 80/443 bị chặn | Kiểm tra DNS, firewall |
| Đăng nhập Google báo lỗi | Redirect URI chưa khai báo `https://<domain>/login/oauth2/code/google` | Cập nhật trong Google Cloud Console |

## Xoay khóa
- JWT: đổi `APP_JWT_SECRET`, khởi động lại - mọi phiên hết hiệu lực.
- PII: chưa hỗ trợ xoay tự động (định dạng bản mã có byte phiên bản để bổ sung sau). Lập ADR trước khi xoay.

## Sự cố dữ liệu cá nhân
Ghi nhận thời điểm phát hiện, phạm vi dữ liệu bị ảnh hưởng, thông báo cho khách hàng (bên kiểm soát dữ liệu) ngay để họ thực hiện nghĩa vụ thông báo theo quy định.
