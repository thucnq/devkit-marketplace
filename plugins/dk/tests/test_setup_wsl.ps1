# Tests for the pure parts of setup-wsl.ps1 (parse + .wslconfig editing). Runs on Linux pwsh in CI.
# Run: pwsh -NoProfile -File plugins/dk/tests/test_setup_wsl.ps1
$src = Join-Path $PSScriptRoot "../scripts/windows/setup-wsl.ps1"
$errs = $null
[System.Management.Automation.Language.Parser]::ParseFile($src, [ref]$null, [ref]$errs) | Out-Null
if ($errs.Count) { $errs | ForEach-Object { "PARSE {0}:{1} {2}" -f $_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Message }; exit 1 }
# Windows PowerShell 5.1 has no ternary / null-coalescing / pipeline-chain operators
$tokens = $null
[System.Management.Automation.Language.Parser]::ParseFile($src, [ref]$tokens, [ref]$null) | Out-Null
$ps7 = $tokens | Where-Object { $_.Kind -in 'QuestionMark','QuestionQuestion','QuestionQuestionEquals','AndAnd','OrOr','QuestionDot','QuestionLBracket' }
if ($ps7) { $ps7 | ForEach-Object { "PS7-ONLY {0}:{1} {2}" -f $_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Text }; exit 1 }
"ok   parses, no PowerShell 7-only operators"
$ast = [System.Management.Automation.Language.Parser]::ParseFile($src, [ref]$null, [ref]$null)
foreach ($f in $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)) {
  if ($f.Name -in 'Set-SwapLocation','Format-GB') { . ([scriptblock]::Create($f.Extent.Text)) }
}
$fail = 0
function Check($name, $cond) { if ($cond) { "ok   $name" } else { "FAIL $name"; $script:fail++ } }
$env:USERPROFILE = Join-Path ([IO.Path]::GetTempPath()) ("wslcfg-" + [guid]::NewGuid())
New-Item -ItemType Directory $env:USERPROFILE | Out-Null
$cfg = Join-Path $env:USERPROFILE ".wslconfig"

# 1. CRLF file with [wsl2] → swapFile inserted right after, CRLF kept, escaped backslashes
Set-Content $cfg -Value "[wsl2]`r`nmemory=8GB`r`nswap=4GB" -NoNewline
Set-SwapLocation 'D:\wsl'
$t = Get-Content $cfg -Raw
Check "inserted after [wsl2] (CRLF)" ($t.StartsWith("[wsl2]`r`nswapFile=D:\\wsl\\swap.vhdx`r`nmemory=8GB"))
Check "no stray CR" (-not $t.Contains("`r`r"))

# 2. existing swapFile → untouched
$before = $t; Set-SwapLocation 'E:\other'
Check "keeps existing swapFile" ((Get-Content $cfg -Raw) -eq $before)

# 3. LF file without [wsl2] section → section appended
Set-Content $cfg -Value "[experimental]`nautoMemoryReclaim=gradual`n" -NoNewline
Set-SwapLocation 'D:\wsl'
$t = Get-Content $cfg -Raw
Check "appends [wsl2] section" ($t -match "\[wsl2\]\r?\nswapFile=D:\\\\wsl\\\\swap\.vhdx")
Check "keeps other sections" ($t.Contains("autoMemoryReclaim=gradual"))

# 4. Drive normalisation used by Resolve-TargetDir
Check "D: → D:\wsl" ("$('d:'.TrimEnd(':','\').ToUpper()):\wsl" -eq 'D:\wsl')
Check "D\ → D:\wsl" ("$('D\'.TrimEnd(':','\').ToUpper()):\wsl" -eq 'D:\wsl')
Check "Format-GB" ((Format-GB 5GB) -match '^5[.,]0 GB$')
Remove-Item -Recurse -Force $env:USERPROFILE
exit $fail
