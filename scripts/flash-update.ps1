#Requires -Version 5.1
<#
.SYNOPSIS
  使用 upgrade_tool 命令行烧写 Rockchip update.img
.EXAMPLE
  .\flash-update.ps1
  .\flash-update.ps1 -Image D:\fw\update.img
  .\flash-update.ps1 -Image .\firmware\update.img -EraseFirst -NoReset
#>
param(
    [Parameter(Position = 0)]
    [string]$Image,

    [switch]$EraseFirst,
    [switch]$NoReset,
    [switch]$SkipConfirm
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Tool = Join-Path $Root "tools\upgrade_tool\upgrade_tool.exe"
$DefaultImage = Join-Path $Root "firmware\update.img"

if (-not (Test-Path $Tool)) {
    Write-Error "找不到 upgrade_tool.exe：$Tool"
}

if (-not $Image) {
    $Image = $DefaultImage
}

if (-not (Test-Path $Image)) {
    Write-Host ""
    Write-Host "未找到固件：$Image"
    Write-Host "用法："
    Write-Host "  .\flash-update.ps1 -Image C:\path\to\update.img"
    Write-Host "或把 update.img 放到：$DefaultImage"
    exit 1
}

$Image = (Resolve-Path $Image).Path

Write-Host "========================================"
Write-Host " Rockchip CLI 固件升级"
Write-Host "========================================"
Write-Host "工具: $Tool"
Write-Host "固件: $Image"
Write-Host ""

Write-Host "[1/3] 检测设备 (LD) ..."
& $Tool LD
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "未检测到 Rockusb 设备。请确认："
    Write-Host "  1. 已安装 tools\DriverAssistant 中的驱动"
    Write-Host "  2. 设备已进入 Loader 或 Maskrom 模式"
    Write-Host "  3. USB 线已连接（尽量用直连口，避免 Hub）"
    exit 1
}

if (-not $SkipConfirm) {
    Write-Host ""
    $ans = Read-Host "确认开始烧写？输入 Y 继续"
    if ($ans -notin @("Y", "y")) {
        Write-Host "已取消。"
        exit 0
    }
}

if ($EraseFirst) {
    Write-Host ""
    Write-Host "[2/3] 擦除 Flash (EF) ..."
    & $Tool EF $Image
    if ($LASTEXITCODE -ne 0) {
        Write-Error "擦除失败，退出码 $LASTEXITCODE"
    }
} else {
    Write-Host ""
    Write-Host "[2/3] 跳过擦除（如需先擦除，加 -EraseFirst）"
}

Write-Host ""
Write-Host "[3/3] 升级固件 (UF) ..."
if ($NoReset) {
    & $Tool UF $Image -noreset
} else {
    & $Tool UF $Image
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "升级失败，退出码 $LASTEXITCODE"
}

Write-Host ""
Write-Host "升级完成。"
exit 0
