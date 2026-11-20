# 备份 DeskFence 数据到 E 盘，然后用 E 盘临时目录重新打包
$ErrorActionPreference = "Stop"

$src = Join-Path $env:APPDATA "DeskFence"
$dst = "E:\DeskFence-Backup-20261119"

Write-Host "=== 第 1 步：备份数据 ===" -ForegroundColor Cyan
if (-not (Test-Path $src)) {
    Write-Host "源目录不存在：$src" -ForegroundColor Red; exit 1
}
if (Test-Path $dst) {
    Remove-Item -Recurse -Force $dst
}
Copy-Item -Path $src -Destination $dst -Recurse
$size = [math]::Round((Get-ChildItem $dst -Recurse -File | Measure-Object Length).Sum / 1MB, 1)
Write-Host "备份完成：$dst  ($size MB)" -ForegroundColor Green

Write-Host "=== 第 2 步：检查磁盘空间 ===" -ForegroundColor Cyan
Write-Host ("C 盘剩余：{0} MB" -f [math]::Round((Get-PSDrive C).Free / 1MB, 0))
Write-Host ("E 盘剩余：{0} MB" -f [math]::Round((Get-PSDrive E).Free / 1MB, 0))

Write-Host "=== 第 3 步：用 E 盘打包 ===" -ForegroundColor Cyan
$proj = "E:\DESKTOP\桌面整理\deskfence"
$buildRoot = "E:\DeskFence-Build"
$tempDir = "E:\DeskFence-Temp"
if (Test-Path $buildRoot) { Remove-Item -Recurse -Force $buildRoot }
if (Test-Path $tempDir) { Remove-Item -Recurse -Force $tempDir }

# 把 PyInstaller 和 python 解压时的临时目录也指到 E 盘
$env:TEMP = $tempDir
$env:TMP = $tempDir
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

Set-Location $proj
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --log-level WARN `
    --name DeskFence --icon "packaging\app.ico" `
    --add-data "syd.png;." `
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml `
    --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest `
    --distpath "$buildRoot\dist" --workpath "$buildRoot\build" --specpath $buildRoot `
    main.py

Write-Host "=== 打包结果 ===" -ForegroundColor Cyan
if (Test-Path "$buildRoot\dist\DeskFence.exe") {
    $f = Get-Item "$buildRoot\dist\DeskFence.exe"
    Write-Host "exe 生成成功：$([math]::Round($f.Length/1MB,1)) MB" -ForegroundColor Green
    Copy-Item "$buildRoot\dist\DeskFence.exe" "$proj\release\DeskFence.exe" -Force
    Write-Host "已复制到 release\DeskFence.exe"
} else {
    Write-Host "exe 生成失败，看日志：$buildRoot\warn-DeskFence.txt" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 后续步骤 ===" -ForegroundColor Yellow
Write-Host "1. 手动双击 E:\DESKTOP\桌面整理\deskfence\release\DeskFence.exe 启动"
Write-Host "2. 托盘图标 → 设置中心 → 数据目录 → 更改… 选 E 盘其他位置（避免 C 盘）"
Write-Host "3. 备份还在：E:\DeskFence-Backup-20261119  （不动）"
