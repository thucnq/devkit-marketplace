<#
  Chuẩn bị máy Windows 10/11 để chạy Claude Code + plugin dk trong WSL2 (Ubuntu).
  Mở PowerShell bằng "Run as Administrator":
    Set-ExecutionPolicy -Scope Process Bypass
    .\setup-wsl.ps1                                   # Bước 1: cài WSL2 + Ubuntu (hỏi chọn ổ đĩa), ghi .wslconfig
    .\setup-wsl.ps1 -Drive D                          # Cài Ubuntu vào D:\wsl\Ubuntu-24.04 - hoặc CHUYỂN Ubuntu đang có sang ổ D
    .\setup-wsl.ps1 -InstallDir E:\linux              # Như trên, tự chọn thư mục
    .\setup-wsl.ps1 -Status                           # Ubuntu đang nằm ở đâu, nặng bao nhiêu, các ổ còn trống bao nhiêu
    .\setup-wsl.ps1 -Configure -RepoPath "~/qldn"     # Bước 3: không ngủ khi cắm điện + tự chạy Remote Control khi đăng nhập
    .\setup-wsl.ps1 -Firewall                         # Chỉ khi IntelliJ debug/attach từ WSL bị chặn
    .\setup-wsl.ps1 -Remove -RepoPath "~/qldn"        # Gỡ tác vụ tự chạy
  Thêm -Yes để không hỏi xác nhận. -MoveTo D:\wsl vẫn dùng được (giống -InstallDir).
  Bước 2 (trong Ubuntu) xem docs/dev/wsl-intellij.md của dự án.

  Đặt Ubuntu ở ổ khác C: cả đĩa ảo (ext4.vhdx, chứa repo, Docker image, Maven/npm cache - thường 20–60 GB)
  lẫn file swap của WSL đều nằm ở ổ đã chọn. Ổ C đầy là nguyên nhân hay gặp nhất làm hỏng đĩa ảo
  ("Bus error", Wsl/Service/CreateInstance/E_FAIL).
#>
param(
  [switch]$Configure,
  [switch]$Remove,
  [switch]$Firewall,
  [switch]$Status,
  [switch]$Yes,
  [string]$Drive = "",
  [string]$InstallDir = "",
  [string]$MoveTo = "",
  [string]$Distro = "Ubuntu-24.04",
  [string]$RepoPath = "~/qldn",
  [int]$MemoryGB = 0
)
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"   # wsl.exe mới in UTF-8 thay vì UTF-16 để đọc được output
$Slug = (Split-Path $RepoPath -Leaf)
$TaskName = "dk-remote-$Slug"

function Assert-Admin {
  $id = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
  if (-not $id.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Hãy mở PowerShell bằng 'Run as Administrator'."
  }
}

function Confirm-Step([string]$question) {
  if ($Yes) { return $true }
  $a = Read-Host "$question (y/N)"
  return ($a -match '^(y|yes|c|co|có)$')
}

function Invoke-Wsl([string[]]$WslArgs) {
  # Không chuyển hướng stderr: trong Windows PowerShell 5.1 + Stop, stderr của lệnh native bị coi là lỗi.
  & wsl.exe @WslArgs | Out-Host
  return $LASTEXITCODE
}

function Get-WslVersion {
  try { $out = (& wsl.exe --version 2>$null | Out-String) -replace "`0", "" } catch { return $null }
  if ($out -match '(\d+)\.(\d+)\.(\d+)') { return [version]"$($Matches[1]).$($Matches[2]).$($Matches[3])" }
  return $null   # WSL có sẵn trong Windows (bản cũ, không có --version)
}

function Get-DistroInfo([string]$name) {
  $root = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss"
  if (-not (Test-Path $root)) { return $null }
  foreach ($k in Get-ChildItem $root) {
    $p = Get-ItemProperty $k.PSPath
    if ($p.DistributionName -eq $name) {
      $base = ($p.BasePath -replace '^\\\\\?\\', '').TrimEnd('\')
      $vhd = Join-Path $base "ext4.vhdx"
      $size = 0
      if (Test-Path $vhd) { $size = (Get-Item $vhd).Length }
      return [pscustomobject]@{ Name = $name; BasePath = $base; Vhd = $vhd; SizeBytes = $size }
    }
  }
  return $null
}

function Get-DataVolumes {
  Get-Volume | Where-Object { $_.DriveLetter -and $_.DriveType -eq 'Fixed' -and ($_.FileSystem -in @('NTFS', 'ReFS')) } |
    Sort-Object DriveLetter
}

function Format-GB([double]$bytes) { return ("{0:N1} GB" -f ($bytes / 1GB)) }

function Show-Volumes {
  Write-Host "  Ổ đĩa dùng được (Fixed, NTFS/ReFS):"
  foreach ($v in Get-DataVolumes) {
    Write-Host ("    {0}:  trống {1,9} / {2,9}  {3}" -f $v.DriveLetter, (Format-GB $v.SizeRemaining), (Format-GB $v.Size), $v.FileSystemLabel)
  }
}

function Resolve-TargetDir {
  # -InstallDir / -MoveTo thắng -Drive. Trả về thư mục cha (vd D:\wsl); đĩa ảo nằm ở <thư mục>\<Distro>.
  $dir = if ($InstallDir) { $InstallDir } elseif ($MoveTo) { $MoveTo } elseif ($Drive) { "$($Drive.TrimEnd(':','\').ToUpper()):\wsl" } else { "" }
  if (-not $dir) { return "" }
  $dir = [IO.Path]::GetFullPath($dir)
  $letter = $dir.Substring(0, 1).ToUpper()
  $vol = Get-Volume -DriveLetter $letter -ErrorAction SilentlyContinue
  if (-not $vol) { throw "Không thấy ổ ${letter}:. Kiểm tra lại tên ổ (Get-Volume)." }
  if ($vol.FileSystem -notin @('NTFS', 'ReFS')) { throw "Ổ ${letter}: là $($vol.FileSystem) - WSL cần NTFS hoặc ReFS (FAT32/exFAT không chứa được đĩa ảo)." }
  if ($vol.DriveType -ne 'Fixed') {
    Write-Host "⚠ Ổ ${letter}: là ổ $($vol.DriveType) (USB/ổ rời). Rút ổ khi WSL đang chạy sẽ hỏng đĩa ảo."
    if (-not (Confirm-Step "Vẫn dùng ổ ${letter}:?")) { exit 1 }
  }
  return $dir
}

function Select-TargetDirInteractive {
  # Chỉ hỏi khi cài mới mà người dùng chưa chọn ổ. Mặc định: ổ khác C trống nhiều nhất nếu C còn < 40 GB.
  $vols = @(Get-DataVolumes)
  if ($vols.Count -le 1) { return "" }
  $c = $vols | Where-Object { $_.DriveLetter -eq 'C' }
  $best = $vols | Where-Object { $_.DriveLetter -ne 'C' } | Sort-Object SizeRemaining -Descending | Select-Object -First 1
  $default = 'C'
  if ($c -and $best -and $c.SizeRemaining -lt 40GB -and $best.SizeRemaining -gt $c.SizeRemaining) { $default = [string]$best.DriveLetter }
  Write-Host ""
  Write-Host "Chọn ổ đặt Ubuntu (đĩa ảo sẽ lớn dần tới 20–60 GB: repo, Docker image, Maven/npm cache)."
  Show-Volumes
  if ($Yes) { $ans = $default } else { $ans = Read-Host "Ổ đĩa [$default]" }
  if (-not $ans) { $ans = $default }
  $ans = $ans.TrimEnd(':', '\').ToUpper()
  if ($ans -eq 'C') { return "" }
  return "${ans}:\wsl"
}

function Set-SwapLocation([string]$targetDir) {
  # File swap của WSL mặc định nằm ở %TEMP% trên ổ C - đưa sang cùng ổ với đĩa ảo.
  $cfg = Join-Path $env:USERPROFILE ".wslconfig"
  $swap = ($targetDir.TrimEnd('\') + '\swap.vhdx') -replace '\\', '\\'
  if (-not (Test-Path $cfg)) { return }
  $text = Get-Content $cfg -Raw
  if ($text -match '(?m)^\s*swapFile\s*=') {
    Write-Host "  .wslconfig đã có swapFile - giữ nguyên (đổi tay nếu nó đang ở ổ C)."
    return
  }
  if ($text -match '(?m)^[ \t]*\[wsl2\][ \t]*\r?$') {
    # giữ kiểu xuống dòng của file (CRLF hoặc LF)
    $text = $text -replace '(?m)^([ \t]*\[wsl2\][ \t]*)(\r?)$', "`$1`$2`nswapFile=$swap`$2"
  } else {
    $text = $text.TrimEnd() + "`r`n[wsl2]`r`nswapFile=$swap`r`n"
  }
  Set-Content -Path $cfg -Value $text -Encoding ASCII
  Write-Host "  Đã đặt swapFile=$swap trong $cfg (có hiệu lực sau wsl --shutdown)."
}

function Move-Distro($info, [string]$targetDir) {
  $dest = Join-Path $targetDir $Distro
  if ($info.BasePath.TrimEnd('\') -ieq $dest.TrimEnd('\')) {
    Write-Host "✓ $Distro đã nằm ở $dest"
    return
  }
  $letter = $dest.Substring(0, 1)
  $free = (Get-Volume -DriveLetter $letter).SizeRemaining
  $need = [math]::Max($info.SizeBytes * 1.2, 2GB)
  Write-Host "== Chuyển ${Distro}: $($info.BasePath) ($(Format-GB $info.SizeBytes)) → $dest (ổ ${letter}: trống $(Format-GB $free)) =="
  if ($free -lt $need) { throw "Ổ ${letter}: không đủ chỗ: cần ~$(Format-GB $need), còn $(Format-GB $free)." }
  if (Test-Path $dest) {
    if (@(Get-ChildItem $dest -Force).Count -gt 0) { throw "$dest đã tồn tại và không rỗng - chọn thư mục khác hoặc dọn thư mục này trước." }
  }
  if (-not (Confirm-Step "Sẽ TẮT toàn bộ WSL (Docker, Claude Code, tmux trong Ubuntu dừng lại). Tiếp tục?")) { exit 1 }
  New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

  # Cách 1: WSL ≥ 2.3 chuyển tại chỗ, giữ nguyên user mặc định và mọi thứ bên trong.
  Invoke-Wsl @('--shutdown') | Out-Null
  $code = Invoke-Wsl @('--manage', $Distro, '--move', $dest)
  if ($code -eq 0) {
    $after = Get-DistroInfo $Distro
    Write-Host "✓ Đã chuyển xong: $(if ($after) { $after.Vhd } else { $dest })"
    return
  }

  # Cách 2 (WSL cũ): export ra file tar trên ổ đích → unregister → import. Không xóa gì trước khi bản tar đã đủ.
  Write-Host "wsl --manage --move không dùng được (WSL cũ). Chuyển bằng export/import - lâu hơn, cần ~2 lần dung lượng ở ổ đích."
  $need2 = [math]::Max($info.SizeBytes * 2.2, 4GB)
  if ($free -lt $need2) { throw "Ổ ${letter}: cần ~$(Format-GB $need2) cho export/import, còn $(Format-GB $free). Hoặc chạy 'wsl --update' rồi thử lại (cách 1 không cần chỗ trống gấp đôi)." }
  $user = ((& wsl.exe -d $Distro -- whoami) | Out-String).Trim()
  Invoke-Wsl @('--shutdown') | Out-Null
  $tar = Join-Path $targetDir "$Distro-backup.tar"
  Write-Host "  Export → $tar (có thể mất vài phút)…"
  if ((Invoke-Wsl @('--export', $Distro, $tar)) -ne 0 -or -not (Test-Path $tar) -or (Get-Item $tar).Length -lt 50MB) {
    throw "Export thất bại - chưa xóa gì, $Distro vẫn nguyên ở $($info.BasePath)."
  }
  Write-Host "  Bản sao lưu: $tar ($(Format-GB (Get-Item $tar).Length))"
  if (-not (Confirm-Step "Gỡ bản $Distro ở $($info.BasePath) rồi import từ bản sao lưu sang $dest?")) {
    Write-Host "Đã dừng. Bản sao lưu giữ ở $tar."; exit 1
  }
  if ((Invoke-Wsl @('--unregister', $Distro)) -ne 0) { throw "Unregister thất bại - $Distro vẫn ở chỗ cũ, bản sao lưu ở $tar." }
  if ((Invoke-Wsl @('--import', $Distro, $dest, $tar, '--version', '2')) -ne 0) {
    throw "Import thất bại. Dữ liệu an toàn trong $tar - chạy lại tay: wsl --import $Distro $dest $tar --version 2"
  }
  if ($user -and $user -ne 'root') {
    # Sau import, user mặc định là root - đặt lại user cũ qua /etc/wsl.conf.
    $sh = "grep -q '^\[user\]' /etc/wsl.conf 2>/dev/null || printf '\n[user]\ndefault=%s\n' '$user' >> /etc/wsl.conf"
    Invoke-Wsl @('-d', $Distro, '-u', 'root', '--', 'sh', '-c', $sh) | Out-Null
    Invoke-Wsl @('--terminate', $Distro) | Out-Null
  }
  $check = ((& wsl.exe -d $Distro -- whoami) | Out-String).Trim()
  Write-Host "✓ $Distro chạy lại được ở $dest (user: $check)"
  if (Confirm-Step "Xóa bản sao lưu $tar để lấy lại chỗ trống?") { Remove-Item $tar -Force; Write-Host "  Đã xóa $tar" }
}

function Show-Status {
  Write-Host "== Trạng thái WSL =="
  $v = Get-WslVersion
  Write-Host ("  WSL: " + $(if ($v) { $v } else { "bản có sẵn trong Windows (cũ) - nên chạy wsl --update" }))
  $info = Get-DistroInfo $Distro
  if ($info) { Write-Host "  $Distro`: $($info.Vhd) ($(Format-GB $info.SizeBytes))" } else { Write-Host "  $Distro`: chưa cài" }
  $cfg = Join-Path $env:USERPROFILE ".wslconfig"
  if (Test-Path $cfg) {
    $swap = Select-String -Path $cfg -Pattern '^\s*swapFile\s*=' | Select-Object -First 1
    Write-Host ("  swapFile: " + $(if ($swap) { $swap.Line.Split('=', 2)[1].Trim() } else { "mặc định (%TEMP% trên ổ C)" }))
  }
  Show-Volumes
}

Assert-Admin

if ($Status) { Show-Status; exit 0 }

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

if ($MoveTo) {
  # Tương thích bản cũ: -MoveTo chỉ chuyển, không cài.
  $target = Resolve-TargetDir
  $info = Get-DistroInfo $Distro
  if (-not $info) { throw "$Distro chưa cài - dùng: .\setup-wsl.ps1 -InstallDir $MoveTo" }
  Move-Distro $info $target
  Set-SwapLocation $target
  exit 0
}

if (-not $Configure) {
  $build = [int](Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber
  if ($build -lt 19041) { throw "WSL2 cần Windows 10 bản 2004 (build 19041) trở lên. Máy đang ở build $build - chạy Windows Update trước." }
  # Ảo hóa phần cứng tắt trong BIOS → lỗi HCS_E_HYPERV_NOT_INSTALLED / 0x80370102 về sau (runbook hopnhat)
  $virt = (Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled
  $hv = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
  if (-not $virt -and -not $hv) {
    throw "Ảo hóa phần cứng đang TẮT. Vào BIOS bật Intel VT-x / AMD SVM, rồi chạy lại script này."
  }

  # WSL mới trước: cần cho 'wsl --install --location' và 'wsl --manage --move'. Máy chưa có WSL thì lệnh này lỗi - bỏ qua.
  try { wsl.exe --update | Out-Host } catch { }

  $target = Resolve-TargetDir
  $info = Get-DistroInfo $Distro
  if ($info) {
    # Đã cài: chỉ chuyển khi người dùng chọn ổ/thư mục.
    Write-Host "$Distro đã cài ở $($info.BasePath) ($(Format-GB $info.SizeBytes))."
    if ($target) {
      Move-Distro $info $target
    } elseif ($info.BasePath -match '^[Cc]:') {
      $c = Get-Volume -DriveLetter C
      if ($c.SizeRemaining -lt 20GB) {
        Write-Host "⚠ Ổ C còn $(Format-GB $c.SizeRemaining). Chuyển Ubuntu sang ổ khác: .\setup-wsl.ps1 -Drive D"
      }
    }
  } else {
    if (-not $target) { $target = Select-TargetDirInteractive }
    Write-Host "== Cài WSL2 + $Distro (Windows build $build)$(if ($target) { " vào $target\$Distro" }) =="
    $installed = $false
    if ($target) {
      New-Item -ItemType Directory -Force -Path $target | Out-Null
      # WSL ≥ 2.4: cài thẳng vào ổ đã chọn, không chiếm chỗ trên C.
      $code = Invoke-Wsl @('--install', '-d', $Distro, '--location', (Join-Path $target $Distro), '--no-launch')
      if ($code -eq 0) { $installed = $true }
      else { Write-Host "WSL chưa hỗ trợ --location (hoặc WSL chưa được bật). Cài theo cách thường, sẽ chuyển sang $target sau." }
    }
    if (-not $installed) {
      $ok = $true
      try { wsl.exe --install -d $Distro | Out-Host } catch { $ok = $false }
      if (-not $ok -or $LASTEXITCODE -ne 0) {
        Write-Host "wsl --install không chạy được (Windows 10 bản cũ). Bật tính năng thủ công:"
        dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
        dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
        bcdedit /set hypervisorlaunchtype auto | Out-Null
        Write-Host "RESTART máy (không chọn Shut down), cài 'WSL2 Linux kernel update package' từ Microsoft, rồi chạy lại:"
        Write-Host "  .\setup-wsl.ps1$(if ($target) { " -InstallDir $target" })"
      }
    }
    # Windows PowerShell 5.1 + ErrorActionPreference=Stop: stderr của lệnh native có thể thành lỗi dừng script
    try { wsl.exe --set-default-version 2 | Out-Null } catch { }
    $info = Get-DistroInfo $Distro
    if ($target -and $info -and ($info.BasePath -notlike "$target*")) {
      Move-Distro $info $target   # cài theo cách thường xong (WSL cũ) → chuyển ngay
    } elseif ($target -and -not $info) {
      Write-Host "Ubuntu sẽ đăng ký sau khi khởi động lại máy / mở Ubuntu lần đầu."
      Write-Host "Khi đó chạy lại: .\setup-wsl.ps1 -InstallDir $target   (script sẽ chuyển Ubuntu sang $target nếu nó nằm ở C)"
    }
  }

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
  if ($target) { Set-SwapLocation $target }

  Write-Host ""
  Show-Status
  Write-Host ""
  Write-Host "Tiếp theo: khởi động lại nếu Windows yêu cầu → mở '$Distro' từ Start menu (hoặc gõ: wsl -d $Distro) → tạo user Linux"
  Write-Host "→ làm Bước 2 trong docs/dev/wsl-intellij.md → quay lại chạy: .\setup-wsl.ps1 -Configure -RepoPath '~/<du-an>'"
  exit 0
}

Write-Host "== Không ngủ / ngủ đông khi cắm điện (Remote Control cần máy thức) =="
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
Write-Host "  Màn hình vẫn tắt bình thường; chạy pin vẫn ngủ."

Write-Host "== Tác vụ '$TaskName': khi đăng nhập Windows → chạy Claude Code Remote Control trong tmux (WSL) =="
$cmd = "cd $RepoPath && ~/.local/bin/dk-remote start; exec sleep infinity"  # giữ WSL sống: không còn wsl.exe nào thì Ubuntu (tmux, claude) bị tắt. Cửa sổ thu nhỏ, không đóng
$action   = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d $Distro -- bash -lc `"$cmd`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description "dk: claude remote-control trong tmux cho $RepoPath" -Force | Out-Null
Write-Host "  Chạy thử: Start-ScheduledTask -TaskName $TaskName ; rồi trong Ubuntu: tmux ls"
Write-Host "  (Cần đã chạy '/dk:doctor' → 'bash .../wsl-doctor.sh --install-launcher' trong Ubuntu để có ~/.local/bin/dk-remote)"
