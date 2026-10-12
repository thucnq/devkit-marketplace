<#
  Chuẩn bị máy Windows 10/11 để chạy Claude Code + plugin dk trong WSL2 (Ubuntu).
  Mở PowerShell bằng "Run as Administrator":
    Set-ExecutionPolicy -Scope Process Bypass
    .\setup-wsl.ps1                                   # Bước 1: cài WSL2 + Ubuntu, ghi .wslconfig
    .\setup-wsl.ps1 -Configure -RepoPath "~/qldn"     # Bước 3: không ngủ khi cắm điện + tự chạy Remote Control khi đăng nhập
    .\setup-wsl.ps1 -Firewall                         # Chỉ khi IntelliJ debug/attach từ WSL bị chặn
    .\setup-wsl.ps1 -Remove -RepoPath "~/qldn"        # Gỡ tác vụ tự chạy
  Bước 2 (trong Ubuntu) xem docs/dev/wsl-intellij.md của dự án.
#>
param(
  [switch]$Configure,
  [switch]$Remove,
  [switch]$Firewall,
  [string]$Distro = "Ubuntu-24.04",
  [string]$RepoPath = "~/qldn",
  [int]$MemoryGB = 0
)
$ErrorActionPreference = "Stop"
$Slug = (Split-Path $RepoPath -Leaf)
$TaskName = "dk-remote-$Slug"

function Assert-Admin {
  $id = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
  if (-not $id.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Hãy mở PowerShell bằng 'Run as Administrator'."
  }
}
Assert-Admin

if ($Remove) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Đã gỡ tác vụ $TaskName"
  exit 0
}

if ($Firewall) {
  # Windows 10: lưu lượng từ WSL2 vào Windows đi qua card "vEthernet (WSL)" và có thể bị firewall chặn
  # (debugger ở chế độ listen, IntelliJ chạy JVM trong WSL). Cho phép riêng card này.
  New-NetFirewallRule -DisplayName "WSL inbound (dk)" -Direction Inbound -InterfaceAlias "vEthernet (WSL)" -Action Allow -ErrorAction SilentlyContinue | Out-Null
  Write-Host "Đã thêm rule firewall cho vEthernet (WSL). Nếu card mang tên khác: Get-NetAdapter | ? Name -like '*WSL*'"
  exit 0
}

if (-not $Configure) {
  $build = [int](Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber
  if ($build -lt 19041) { throw "WSL2 cần Windows 10 bản 2004 (build 19041) trở lên. Máy đang ở build $build — chạy Windows Update trước." }

  Write-Host "== Cài WSL2 + $Distro (Windows build $build) =="
  $ok = $true
  try { wsl --install -d $Distro } catch { $ok = $false }
  if (-not $ok -or $LASTEXITCODE -ne 0) {
    Write-Host "wsl --install không chạy được (Windows 10 bản cũ). Bật tính năng thủ công:"
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    Write-Host "Khởi động lại máy, cài 'WSL2 Linux kernel update package' từ Microsoft, rồi chạy:"
    Write-Host "  wsl --set-default-version 2 ; wsl --install -d $Distro   (hoặc cài Ubuntu 24.04 từ Microsoft Store)"
  }
  # Windows PowerShell 5.1 + ErrorActionPreference=Stop: stderr của lệnh native có thể thành lỗi dừng script
  try { wsl --set-default-version 2 | Out-Null } catch { }
  try { wsl --update | Out-Null } catch { Write-Host "wsl --update không chạy được (bỏ qua)" }

  # Giới hạn RAM cho WSL: Windows 10 + IntelliJ + Docker dễ hết RAM nếu để mặc định
  $cfg = Join-Path $env:USERPROFILE ".wslconfig"
  if (-not (Test-Path $cfg)) {
    $totalGB = [math]::Floor((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    if ($MemoryGB -le 0) { $MemoryGB = [math]::Max(4, [math]::Min(12, [math]::Floor($totalGB / 2))) }
    $cpu = [math]::Max(2, [Environment]::ProcessorCount - 2)
    @"
[wsl2]
memory=${MemoryGB}GB
processors=$cpu
swap=4GB
localhostForwarding=true
"@ | Set-Content -Path $cfg -Encoding ASCII
    Write-Host "Đã ghi $cfg (RAM ${MemoryGB}GB / máy ${totalGB}GB, $cpu CPU). Sửa xong thì chạy: wsl --shutdown"
  } else {
    Write-Host "Giữ nguyên $cfg đã có."
  }
  Write-Host ""
  Write-Host "Tiếp theo: khởi động lại nếu Windows yêu cầu → mở '$Distro' từ Start menu → tạo user Linux"
  Write-Host "→ làm Bước 2 trong docs/dev/wsl-intellij.md → quay lại chạy: .\setup-wsl.ps1 -Configure -RepoPath '~/<du-an>'"
  exit 0
}

Write-Host "== Không ngủ / ngủ đông khi cắm điện (Remote Control cần máy thức) =="
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
Write-Host "  Màn hình vẫn tắt bình thường; chạy pin vẫn ngủ."

Write-Host "== Tác vụ '$TaskName': khi đăng nhập Windows → chạy Claude Code Remote Control trong tmux (WSL) =="
$cmd = "cd $RepoPath && ~/.local/bin/dk-remote start"
$action   = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d $Distro -- bash -lc `"$cmd`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "dk: claude remote-control trong tmux cho $RepoPath" -Force | Out-Null
Write-Host "  Chạy thử: Start-ScheduledTask -TaskName $TaskName ; rồi trong Ubuntu: tmux ls"
Write-Host "  (Cần đã chạy '/dk:doctor' → 'bash .../wsl-doctor.sh --install-launcher' trong Ubuntu để có ~/.local/bin/dk-remote)"
