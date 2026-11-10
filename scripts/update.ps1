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
Start-Sleep -Seconds 5
(Get-Service $Service).Status

Write-Host "`n=== 確認網站 ===" -ForegroundColor Cyan
try {
    $r = Invoke-WebRequest 'http://127.0.0.1:8000/' -UseBasicParsing -MaximumRedirection 0 -ErrorAction Stop
    $code = $r.StatusCode
} catch {
    $code = [int]$_.Exception.Response.StatusCode
}
if ($code -in 200, 301, 302) { Write-Host "網站有回應（$code）。更新完成：$before → $after" -ForegroundColor Green }
else { throw "網站沒有正常回應（$code），請看 $Base\logs\web.log" }
