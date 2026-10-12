# Làm việc trên Windows 10/11: Claude Code trong WSL2, code và debug bằng IntelliJ

> Áp dụng cho mọi dự án dk. Mục tiêu: **mọi thứ chạy trong Ubuntu (WSL2)** — Claude Code, agent, hook, Maven, Docker, Node, git. Windows chỉ chạy IntelliJ và trình duyệt.

```
Windows 10/11                                   WSL2 · Ubuntu 24.04 (ext4)
┌──────────────────────────────┐                ┌──────────────────────────────────────────┐
│ IntelliJ IDEA                │  \\wsl$\…      │ ~/<du-an>   (repo — KHÔNG đặt ở /mnt/c)   │
│  ├ mở project qua \\wsl$     │ ─────────────► │ JDK 21 · Maven · Node 22 · git · gh      │
│  ├ JDK = JDK của WSL         │                │ Docker Engine → Postgres, Testcontainers │
│  └ Debug: localhost:5005     │ ◄── localhost ─│ claude (CLI) + plugin dk + hook          │
│ Trình duyệt: localhost:5173  │   forwarding   │ tmux: claude remote-control (điện thoại) │
└──────────────────────────────┘                └──────────────────────────────────────────┘
```

## Vì sao bỏ chạy trực tiếp trên Windows
| Lỗi đã gặp trên Windows | Nguyên nhân | Trong WSL |
|---|---|---|
| Script `.sh` báo `\r: command not found` | Git for Windows đổi LF → CRLF | `.gitattributes` ép LF, `core.autocrlf=input` |
| File mất quyền thực thi sau khi giải nén/checkout | NTFS không có bit `x` | ext4 giữ quyền |
| Hook, `python3`, `bash` khác hành vi | Git Bash/MSYS không phải Linux thật | Linux thật, giống CI (ubuntu-latest) |
| Testcontainers, Docker chậm hoặc không chạy | Docker Desktop + đường dẫn Windows | Docker Engine ngay trong Ubuntu |
| Maven/npm chậm | Antivirus quét `node_modules`, `target` | ext4 nhanh hơn nhiều lần |

`/dk:doctor` kiểm tra toàn bộ điều kiện dưới đây; phiên Claude Code cũng tự cảnh báo nếu đang chạy trên Git Bash hoặc repo nằm dưới `/mnt/c`.

---

## Bước 1 — Cài WSL2 (PowerShell, Run as Administrator)

Điều kiện: Windows 10 bản 2004 (build 19041) trở lên — kiểm tra bằng `winver`. Bật ảo hóa (VT-x/AMD-V) trong BIOS nếu `wsl` báo lỗi `0x80370102`.

Lấy `setup-wsl.ps1` từ repo plugin (`plugins/dk/scripts/windows/setup-wsl.ps1` trên GitHub, nút *Download raw file*), lưu vào `Downloads`, rồi:
```powershell
cd $env:USERPROFILE\Downloads
Set-ExecutionPolicy -Scope Process Bypass
.\setup-wsl.ps1
```
Script: cài WSL2 + Ubuntu 24.04 (Windows 10 bản cũ không có `wsl --install` thì tự bật tính năng bằng `dism`), chạy `wsl --update`, và ghi `%USERPROFILE%\.wslconfig` giới hạn RAM (mặc định một nửa RAM máy, tối đa 12 GB) để Windows + IntelliJ không bị đói RAM.

Khởi động lại nếu được yêu cầu → mở **Ubuntu 24.04** từ Start menu → tạo user Linux.

Lưu ý riêng Windows 10: không có *mirrored networking* (chỉ Windows 11 22H2+). Hướng dẫn này chỉ dùng **localhost forwarding** (Windows → WSL), chạy được trên Windows 10.

## Bước 2 — Trong Ubuntu: công cụ, Claude Code, repo

```bash
# systemd (để Docker Engine tự chạy). Nếu vừa thêm: PowerShell `wsl --shutdown`, mở lại Ubuntu
grep -q 'systemd=true' /etc/wsl.conf || printf '[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf

sudo apt update && sudo apt install -y git jq tmux curl unzip openjdk-21-jdk maven \
     docker.io docker-compose-v2 python3-openpyxl gh
sudo usermod -aG docker "$USER" && newgrp docker
sudo systemctl enable --now docker
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs

git config --global core.autocrlf input
git config --global user.name "<Tên>" && git config --global user.email "<email>"
gh auth login                                   # GitHub.com → HTTPS → đăng nhập bằng trình duyệt

curl -fsSL https://claude.ai/install.sh | bash  # Claude Code bản Linux, cài TRONG Ubuntu
claude                                          # /login bằng tài khoản claude.ai (Pro)
```
Trong `claude`, cài plugin (một lần cho mỗi máy):
```
/plugin marketplace add thucnq/devkit-marketplace
/plugin install dk@thuc-devkit
```
Đã dùng Docker Desktop trên Windows? Có thể giữ: bật *Settings → Resources → WSL integration → Ubuntu-24.04* và bỏ `docker.io docker-compose-v2` khỏi lệnh trên. Không dùng cả hai cùng lúc.

Công cụ quét (tùy chọn, thiếu thì kiểm tra tương ứng báo SKIPPED): `gitleaks`, `semgrep` (`pipx install semgrep`), `osv-scanner`, `k6`.

**Clone repo vào filesystem Linux — không đặt ở `/mnt/c/...`:**
```bash
mkdir -p ~/code && cd ~/code && gh repo clone <owner>/<du-an> && cd <du-an>
claude          # rồi gõ: /dk:doctor
```
Repo cũ đang nằm trên ổ C? Đừng chép thư mục sang — `git clone` lại vào `~/code` (tránh mang theo CRLF và quyền file sai). Thay đổi chưa commit thì commit/push trên Windows trước.

File MISA hoặc dữ liệu khách nằm ở Windows: `cp /mnt/c/Users/<tên>/Downloads/*.xlsx docs/input/misa/` (thư mục này đã nằm trong `.gitignore`).

## Bước 3 — (tùy chọn) Remote Control tự chạy khi bật máy

Trong Ubuntu, một lần: `/dk:doctor --install-launcher` (tạo `~/.local/bin/dk-remote`). Thử: `cd ~/code/<du-an> && dk-remote start`, rồi `dk-remote attach` để trả lời câu hỏi lần đầu (Ctrl+B rồi D để rời tmux mà không dừng).

PowerShell (Admin):
```powershell
.\setup-wsl.ps1 -Configure -RepoPath "~/code/<du-an>"
```
Tạo tác vụ `dk-remote-<du-an>` chạy khi đăng nhập Windows và tắt chế độ ngủ khi cắm điện. Lệnh khác: `dk-remote stop | resume | attach`. Windows Update có thể tự khởi động lại máy — đặt *Active hours* rộng.

---

## Bước 4 — IntelliJ IDEA trên Windows

Chọn một trong ba cách. Cách A đủ cho hầu hết trường hợp và chạy được với **Community**.

### Cách A — Mở project qua `\\wsl$`, JDK của WSL (khuyên dùng)
1. *File → Open* → `\\wsl$\Ubuntu-24.04\home\<user>\code\<du-an>` (hoặc `\\wsl.localhost\...`). Chọn *Trust project*.
2. *File → Project Structure → SDKs → + → Add JDK…* → chọn `\\wsl$\Ubuntu-24.04\usr\lib\jvm\java-21-openjdk-amd64`. IntelliJ nhận ra đây là JDK của WSL. Đặt làm *Project SDK*.
3. *Settings → Build, Execution, Deployment → Build Tools → Maven*: *Maven home* = **Use Maven wrapper**; *Runner → JRE* = JDK WSL vừa thêm; *Importing → JDK for importer* = JDK WSL.
4. *Settings → Tools → Terminal → Shell path*: `wsl.exe -d Ubuntu-24.04` — terminal trong IntelliJ là Ubuntu, dùng để chạy `claude`, `npm`, `docker`.
5. *Settings → Version Control → Git*: IntelliJ tự dùng git của WSL cho project trong `\\wsl$`. Nếu ô *Path to Git* đang là `C:\Program Files\Git\…`, đổi thành `\\wsl$\Ubuntu-24.04\usr\bin\git`.
6. *File → Settings → Build → Compiler → Excludes* / nhấp phải thư mục → *Mark Directory as → Excluded*: `frontend/node_modules`, `backend/target`, `.dk/log` — giảm thời gian index qua `\\wsl$`.

**Chạy và debug:** dự án có sẵn cấu hình trong `.run/`, IntelliJ tự nạp:
| Cấu hình | Việc |
|---|---|
| `API (dev)` | Chạy/Debug `Application` với profile `dev`. JVM chạy **trong WSL** (vì SDK là JDK WSL), breakpoint dùng bình thường |
| `Attach API :5005` | Gắn debugger vào API đang chạy bằng `scripts/dev/debug-api.sh` (cách C) |

Trước khi chạy: `docker compose -f deploy/compose.dev.yml up -d` (terminal Ubuntu) để có Postgres. API: http://localhost:8080 · Swagger: http://localhost:8080/swagger-ui.html.

**Chạy test từ IntelliJ:** nhấp vào mũi tên cạnh class test. Testcontainers dùng Docker trong WSL nên chạy được ngay; nếu báo *Could not find a valid Docker environment* → `docker info` trong Ubuntu phải chạy được không cần sudo (đăng nhập lại sau `usermod -aG docker`).

### Cách B — Remote Development vào WSL (IntelliJ Ultimate, máy ≥ 16 GB RAM)
*File → Remote Development → WSL* → chọn Ubuntu-24.04 → chọn thư mục project. Phần nặng của IDE (index, build, chạy) nằm trong WSL, Windows chỉ hiển thị → index nhanh nhất, không cần cấu hình JDK/Git như cách A. Đổi lại tốn RAM hơn (IDE backend chạy trong WSL).

### Cách C — Chạy trong terminal Ubuntu, IntelliJ chỉ gắn debugger (luôn chạy được)
```bash
bash scripts/dev/debug-api.sh              # API + JDWP trên cổng 5005
SUSPEND=y bash scripts/dev/debug-api.sh    # chờ debugger rồi mới khởi động (debug lỗi lúc start)
```
Trong IntelliJ: chọn cấu hình **Attach API :5005** → Debug. Windows 10 chuyển `localhost:5005` vào WSL2 tự động. Cách này hữu ích khi muốn chạy đúng như Claude Code chạy (cùng Maven, cùng biến môi trường), hoặc khi agent đang giữ một tiến trình API mà bạn muốn debug.

Debug test đang fail mà agent báo: `./mvnw -pl backend test -Dtest=NoteApiTest -Dmaven.surefire.debug` (Surefire chờ debugger ở cổng 5005) → *Attach API :5005*.

### Frontend
```bash
npm --prefix frontend ci && npm --prefix frontend run dev    # http://localhost:5173 mở bằng trình duyệt Windows
```
Vite proxy `/api` sang `localhost:8080` trong WSL. Sửa file trong IntelliJ (qua `\\wsl$`) vẫn kích hoạt hot reload. Debug React: DevTools của Chrome/Edge (source map có sẵn); IntelliJ Ultimate có thể tạo cấu hình *JavaScript Debug* trỏ `http://localhost:5173`.

---

## Làm việc cùng Claude Code
- Chạy `claude` trong terminal Ubuntu (hoặc terminal IntelliJ đã đặt `wsl.exe`), ở thư mục gốc repo. **Không** chạy bản `claude` Windows trên cùng repo — hai bản khác nhau về hook và đường dẫn.
- Agent và bạn cùng sửa một cây làm việc: trước khi để agent `/dk:build`, commit hoặc stash việc đang làm trong IntelliJ. IntelliJ tự tải lại file agent đã đổi (*Settings → Appearance & Behavior → System Settings → Synchronize files on frame activation*).
- Mỗi người một nhánh `feat/<feature>`; không làm chung một thư mục giữa hai người.

## Sự cố thường gặp
| Triệu chứng | Cách xử lý |
|---|---|
| `\r: command not found`, `bad interpreter` | `/dk:doctor --fix` (đặt `autocrlf=input`, bỏ CR), commit lại; kiểm tra có `.gitattributes` |
| IntelliJ index rất lâu | Exclude `node_modules`, `target`; hoặc dùng cách B |
| Attach :5005 báo *Connection refused* | API phải chạy bằng `debug-api.sh` (bind `*:5005`, không phải `localhost` của WSL); `ss -ltnp | grep 5005` trong Ubuntu |
| IntelliJ chạy `API (dev)` nhưng debugger không dừng / treo lúc connect | Firewall chặn kết nối từ WSL về Windows: PowerShell Admin `.\setup-wsl.ps1 -Firewall`; hoặc dùng cách C |
| Cổng 5432 / 8080 đã bị dùng | Postgres hoặc dịch vụ khác đang chạy trên Windows: tắt nó, hoặc đổi cổng trong `deploy/compose.dev.yml` |
| WSL ăn hết RAM (`vmmem`) | Giảm `memory=` trong `%USERPROFILE%\.wslconfig`, rồi `wsl --shutdown` |
| `docker: permission denied` | `sudo usermod -aG docker $USER`, đóng mở lại Ubuntu |
| Đồng hồ WSL lệch sau khi máy ngủ (token JWT hết hạn sai, `git` cảnh báo) | `sudo hwclock -s` hoặc `wsl --shutdown` |
| Remote Control không lên trên điện thoại | `dk-remote attach` xem lỗi; máy phải thức, đăng nhập `claude` bằng tài khoản claude.ai (không dùng API key) |
