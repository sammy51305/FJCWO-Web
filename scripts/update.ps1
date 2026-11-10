# FJCWO 正式站一鍵更新（Windows 主機用，見 _notes/DEPLOY-WINDOWS.md 第 12 節）
#
# 用「系統管理員 PowerShell」執行（重啟服務需要管理員權限）：
#     powershell -ExecutionPolicy Bypass -File C:\FJCWO-Web\scripts\update.ps1
#
# 依序：先備份 → git pull（只快轉）→ 安裝套件 → migrate → collectstatic → 重啟服務 → 確認網站有回應。
# 任何一步失敗就停下，不會繼續做後面的步驟；服務只在全部成功後才重啟。

param(
    [string]$BackupDest = 'D:\FJCWO-Backup',
    [string]$Service = 'FJCWO-Web'
)

$ErrorActionPreference = 'Stop'
$Base = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Base 'venv\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'

function Step($name, [scriptblock]$block) {
    Write-Host "`n=== $name ===" -ForegroundColor Cyan
    & $block
    if ($LASTEXITCODE -ne 0) { throw "$name 失敗（exit $LASTEXITCODE），已停止，網站維持原狀。" }
}

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw '請用「以系統管理員身分執行」的 PowerShell 跑這支腳本。' }

Set-Location $Base
$before = git rev-parse --short HEAD

Step '備份' { & $Py scripts\backup.py backup --dest $BackupDest }
Step 'git pull' { git pull --ff-only }
$after = git rev-parse --short HEAD
if ($before -eq $after) { Write-Host "程式碼沒有新版本（$after），仍會重跑後續步驟以防萬一。" }
else { git log --oneline "$before..$after" }

Step '安裝套件' { & $Py -m pip install -r requirements.txt -q }
Step 'migrate' { & $Py manage.py migrate --noinput }
Step 'collectstatic' { & $Py manage.py collectstatic --noinput }

Write-Host "`n=== 重啟服務 ===" -ForegroundColor Cyan
Restart-Service $Service
(Get-Service $Service).Status

Write-Host "`n=== 確認網站 ===" -ForegroundColor Cyan
# 用 Windows 內建的 curl.exe，不用 Invoke-WebRequest：
# 正式站開了 SECURE_SSL_REDIRECT，本機 http 一律回 301；Windows PowerShell 5.1 的
# Invoke-WebRequest -MaximumRedirection 0 遇到 3xx 會丟 InvalidOperationException 且拿不到回應碼（變成 0），
# 網站明明正常卻被判失敗（2026-11-11 實際發生）。curl 不跟轉址，直接回報 301。
# 服務重啟後 Waitress 需要幾秒才開始聽 port，所以最多重試 30 秒，不再固定只等 5 秒。
$code = '000'
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 2
    $code = curl.exe -s -o NUL -w '%{http_code}' --max-time 5 'http://127.0.0.1:8000/'
    if ($code -in '200', '301', '302') { break }
}
if ($code -in '200', '301', '302') { Write-Host "網站有回應（$code）。更新完成：$before → $after" -ForegroundColor Green }
else { throw "網站 30 秒內沒有正常回應（$code；000 代表連不上），請看 $Base\logs\web.log" }
