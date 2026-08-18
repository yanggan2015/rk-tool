#Requires -Version 5.1
# 兼容旧入口：转调 flash.ps1
param(
    [Parameter(Position = 0)]
    [string]$Image,

    [switch]$EraseFirst,
    [switch]$NoReset,
    [switch]$SkipConfirm
)

$flash = Join-Path $PSScriptRoot "flash.ps1"
$pass = @()
if ($Image) { $pass += $Image } else { $pass += "update" }
if ($EraseFirst) { $pass += "-EraseFirst" }
if ($NoReset) { $pass += "-NoReset" }
if ($SkipConfirm) { $pass += "-SkipConfirm" }
& $flash @pass
exit $LASTEXITCODE
