#!/usr/bin/env bash
# Kiểm tra môi trường chạy Claude Code + dk (ưu tiên WSL2 Ubuntu). Không sửa gì trừ khi có cờ.
#   wsl-doctor.sh                     kiểm tra, in OK / WARN / FAIL (exit 1 nếu có FAIL)
#   wsl-doctor.sh --fix               sửa phần an toàn: git core.autocrlf=input, core.fileMode, chuẩn hóa CRLF trong cây làm việc
#   wsl-doctor.sh --install-launcher  tạo ~/.local/bin/dk-remote (dùng cho tác vụ tự khởi động của setup-wsl.ps1)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fails=0; warns=0
ok()   { printf '  OK    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*"; warns=$((warns + 1)); }
fail() { printf '  FAIL  %s\n' "$*"; fails=$((fails + 1)); }
have() { command -v "$1" >/dev/null 2>&1; }
ver_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -1)" = "$2" ]; }

if [ "${1:-}" = "--install-launcher" ]; then
  mkdir -p "$HOME/.local/bin"
  cat > "$HOME/.local/bin/dk-remote" <<EOF
#!/usr/bin/env bash
# Sinh bởi dk wsl-doctor.sh — luôn gọi dk-remote.sh của bản plugin dk mới nhất đã cài.
s="\$(ls -d "\$HOME"/.claude/plugins/cache/*/dk/*/scripts/dk-remote.sh 2>/dev/null | sort -V | tail -1)"
[ -n "\$s" ] || s="$HERE/dk-remote.sh"
exec bash "\$s" "\$@"
EOF
  chmod +x "$HOME/.local/bin/dk-remote"
  echo "Đã tạo ~/.local/bin/dk-remote. Thử: cd ~/<du-an> && dk-remote start"
  exit 0
fi

echo "== Hệ điều hành"
case "$(uname -s)" in
  Linux)
    if grep -qi microsoft /proc/version 2>/dev/null; then
      if uname -r | grep -qi 'microsoft-standard\|WSL2'; then ok "WSL2 ($(. /etc/os-release && echo "$PRETTY_NAME"))"
      else fail "Đang là WSL1 — chuyển sang WSL2: (PowerShell) wsl --set-version <distro> 2"; fi
      [ "$(ps -p 1 -o comm= 2>/dev/null)" = systemd ] && ok "systemd bật" \
        || warn "systemd chưa bật (Docker Engine cần): printf '[boot]\\nsystemd=true\\n' | sudo tee -a /etc/wsl.conf, rồi (PowerShell) wsl --shutdown"
    else ok "Linux"; fi ;;
  MINGW*|MSYS*|CYGWIN*) fail "Đang chạy trên Windows ($(uname -s)) qua Git Bash/MSYS — dk hỗ trợ WSL2. Xem docs/dev/wsl-intellij.md"; ;;
  Darwin) ok "macOS" ;;
  *) warn "Hệ điều hành lạ: $(uname -s)" ;;
esac
mem_kb=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)
[ "${mem_kb:-0}" -ge 5800000 ] && ok "RAM cho Linux: $((mem_kb / 1024 / 1024)) GB" \
  || warn "RAM cho Linux chỉ $((mem_kb / 1024 / 1024)) GB — Testcontainers + Maven + Vite cần ≥ 6 GB (.wslconfig memory=)"

echo "== Repo"
if root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  case "$root" in
    /mnt/[a-z]/*) fail "Repo nằm trên ổ Windows ($root): chậm nhiều lần, sai quyền file, dễ dính CRLF. Clone lại vào ~/ trong WSL." ;;
    *) ok "Repo ở filesystem Linux: $root" ;;
  esac
  ac="$(git config core.autocrlf || echo unset)"
  [ "$ac" = true ] && fail "git core.autocrlf=true — sẽ đổi script sang CRLF. Sửa: wsl-doctor.sh --fix" || ok "git core.autocrlf=$ac"
  if [ -d "$root/.githooks" ]; then
    [ "$(git -C "$root" config core.hooksPath)" = .githooks ] && ok "git hook của dự án đang bật (.githooks)" \
      || warn "git hook của dự án chưa bật cho clone này: git config core.hooksPath .githooks"
  fi
  [ -f "$root/.gitattributes" ] && ok ".gitattributes có" || warn "Thiếu .gitattributes (golden path có mẫu ép LF cho *.sh, *.py, *.yml …)"
  crlf="$(cd "$root" && git ls-files -z -- '*.sh' '*.py' '*.yml' '*.yaml' '*.sql' '*.java' '*.ts' '*.tsx' 'mvnw' 2>/dev/null \
          | xargs -0 -r grep -lI $'\r' 2>/dev/null | head -5)"
  [ -z "$crlf" ] && ok "Không có file nguồn CRLF" || fail "File có CRLF (script sẽ lỗi '\\r: command not found'): $(echo "$crlf" | tr '\n' ' ')— sửa: wsl-doctor.sh --fix"
else
  warn "Không ở trong repo git — bỏ qua kiểm tra repo"
fi

echo "== Công cụ"
if have java; then jv="$(java -version 2>&1 | sed -nE 's/.*version "([0-9]+).*/\1/p' | head -1)"
  [ "${jv:-0}" -ge 21 ] && ok "java $jv" || fail "java $jv < 21: sudo apt install -y openjdk-21-jdk"
else fail "Thiếu java 21: sudo apt install -y openjdk-21-jdk"; fi
{ [ -x "${root:-.}/mvnw" ] && ok "Maven wrapper (./mvnw)"; } || { have mvn && ok "mvn $(mvn -v 2>/dev/null | sed -nE '1s/.* ([0-9.]+).*/\1/p')"; } || warn "Thiếu Maven: sudo apt install -y maven"
if have node; then nv="$(node -v | tr -d v)"; ver_ge "$nv" 22.0.0 && ok "node $nv" || warn "node $nv < 22"
else fail "Thiếu node 22: curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt install -y nodejs"; fi
case "$(command -v node 2>/dev/null)" in /mnt/[a-z]/*) fail "node đang lấy từ Windows ($(command -v node)) — cài node trong Ubuntu";; esac
case "$(command -v java 2>/dev/null)" in /mnt/[a-z]/*) fail "java đang lấy từ Windows — cài JDK trong Ubuntu";; esac
case "$(command -v docker 2>/dev/null)" in /mnt/[a-z]/*) fail "docker đang lấy từ Windows ($(command -v docker)) — đó là Docker Desktop. Cài Docker Engine trong Ubuntu; vẫn ra /mnt/c thì thêm '[interop] appendWindowsPath=false' vào /etc/wsl.conf rồi (PowerShell) wsl --shutdown";; esac
if have docker; then
  if docker info >/dev/null 2>&1; then ok "docker chạy được ($(docker version -f '{{.Server.Version}}' 2>/dev/null))"
  else fail "docker có nhưng không kết nối được daemon: sudo systemctl enable --now docker && sudo usermod -aG docker \$USER (đăng nhập lại), hoặc bật WSL integration trong Docker Desktop"; fi
  docker compose version >/dev/null 2>&1 && ok "docker compose" || warn "Thiếu docker compose v2: sudo apt install -y docker-compose-v2"
else fail "Thiếu docker (Testcontainers cần): sudo apt install -y docker.io docker-compose-v2"; fi
if have python3; then
  python3 -c 'import openpyxl' 2>/dev/null && ok "python3 + openpyxl" || warn "Thiếu openpyxl (báo giá .xlsx): sudo apt install -y python3-openpyxl"
else fail "Thiếu python3"; fi
have git && { gv="$(git --version | awk '{print $3}')"; ver_ge "$gv" 2.31.0 && ok "git $gv" || warn "git $gv < 2.31"; }
have gh && { gh auth status >/dev/null 2>&1 && ok "gh đã đăng nhập" || warn "gh chưa đăng nhập: gh auth login"; } || warn "Thiếu gh: sudo apt install -y gh"
have claude && ok "claude $(claude --version 2>/dev/null | head -1)" || fail "Thiếu Claude Code trong WSL: curl -fsSL https://claude.ai/install.sh | bash"
have tmux && ok "tmux" || warn "Thiếu tmux (Remote Control chạy nền): sudo apt install -y tmux"
# Remote Control chỉ chạy với đăng nhập claude.ai, gọi thẳng api.anthropic.com, feature flag bật (runbook hopnhat 10.3)
rc_block=""
for v in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX \
         CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC DISABLE_GROWTHBOOK; do
  [ -n "${!v:-}" ] && rc_block="$rc_block $v"
done
[ -z "$rc_block" ] && ok "Không có biến môi trường chặn Remote Control" \
  || warn "Biến môi trường làm Remote Control từ chối chạy:$rc_block — bỏ khỏi ~/.bashrc rồi 'claude auth login' bằng tài khoản claude.ai"
for t in gitleaks semgrep osv-scanner k6; do have "$t" && ok "$t" || warn "Thiếu $t (kiểm tra tương ứng sẽ SKIPPED)"; done
[ -x "$HOME/.local/bin/dk-remote" ] && ok "$HOME/.local/bin/dk-remote" || warn "Chưa có ~/.local/bin/dk-remote (cần cho tự khởi động): wsl-doctor.sh --install-launcher"

if [ "${1:-}" = "--fix" ] && [ -n "${root:-}" ]; then
  echo "== Sửa"
  git config --global core.autocrlf input && echo "  git core.autocrlf=input (global)"
  git -C "$root" config core.autocrlf input
  [ -d "$root/.githooks" ] && git -C "$root" config core.hooksPath .githooks && echo "  core.hooksPath=.githooks"
  git -C "$root" config core.fileMode false && echo "  core.fileMode=false (tránh diff do quyền file khi IntelliJ/Windows chạm vào)"
  if [ -n "${crlf:-}" ]; then
    (cd "$root" && git ls-files -z -- '*.sh' '*.py' '*.yml' '*.yaml' '*.sql' '*.java' '*.ts' '*.tsx' 'mvnw' \
      | xargs -0 -r grep -lIZ $'\r' | xargs -0 -r sed -i 's/\r$//')
    echo "  đã bỏ CR ở các file nguồn — kiểm tra 'git status' rồi commit nếu đúng"
  fi
fi

echo "== Kết quả: $fails FAIL, $warns WARN"
[ "$fails" -eq 0 ]
