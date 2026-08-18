#Requires -Version 5.1
<#
.SYNOPSIS
  瑞芯微命令行工具：覆盖 upgrade_tool 手册常用功能。
  整包/分区烧写、擦除、读设备信息、多设备选择、下载 Boot、切 Maskrom、按地址读写、多存储切换。
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Targets,

    [string]$Partition,
    [string]$Image,
    [string]$Loader,
    [Alias("s")]
    [string]$Select,
    [string]$Storage,
    [switch]$EraseFirst,
    [switch]$NoReset,
    [switch]$SkipConfirm,
    [switch]$NoDownloadBoot,
    [switch]$RequireMaskrom,
    [int]$Timeout = 60,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
$ToolDir = Join-Path $Root "tools\upgrade_tool"
$Tool = Join-Path $ToolDir "upgrade_tool.exe"
$FirmwareDir = Join-Path $Root "firmware"
$SavedLoader = Join-Path $FirmwareDir "MiniLoaderAll.bin"
$SavedParameter = Join-Path $FirmwareDir "parameter.txt"

$StorageNames = @("FLASH", "EMMC", "SPINOR", "SPINAND")

# Kind: firmware=整包 UF；loader=写入 MiniLoader(UL)；image=分区 DI
$Catalog = [ordered]@{
    "update"      = @{ Kind = "firmware"; Flag = $null;        Files = @("update.img") }
    "loader"      = @{ Kind = "loader";   Flag = $null;        Files = @("MiniLoaderAll.bin") }
    "parameter"   = @{ Kind = "image";    Flag = "-p";          Files = @("parameter.txt", "parameter") }
    "uboot"       = @{ Kind = "image";    Flag = "-uboot";      Files = @("uboot.img") }
    "trust"       = @{ Kind = "image";    Flag = "-trust";      Files = @("trust.img") }
    "boot"        = @{ Kind = "image";    Flag = "-boot";       Files = @("boot.img") }
    "recovery"    = @{ Kind = "image";    Flag = "-recovery";   Files = @("recovery.img") }
    "rootfs"      = @{ Kind = "image";    Flag = "-rootfs";     Files = @("rootfs.img") }
    "system"      = @{ Kind = "image";    Flag = "-system";     Files = @("system.img") }
    "misc"        = @{ Kind = "image";    Flag = "-misc";       Files = @("misc.img") }
    "resource"    = @{ Kind = "image";    Flag = "-re";         Files = @("resource.img") }
    "kernel"      = @{ Kind = "image";    Flag = "-k";          Files = @("kernel.img") }
    "oem"         = @{ Kind = "image";    Flag = "-oem";        Files = @("oem.img") }
    "userdata"    = @{ Kind = "image";    Flag = "-userdata";   Files = @("userdata.img") }
    "super"       = @{ Kind = "image";    Flag = "-super";      Files = @("super.img") }
    "dtbo"        = @{ Kind = "image";    Flag = "-dtbo";       Files = @("dtbo.img") }
    "vbmeta"      = @{ Kind = "image";    Flag = "-vbmeta";     Files = @("vbmeta.img") }
    "vendor"      = @{ Kind = "image";    Flag = "-vendor";     Files = @("vendor.img") }
    "vendor_boot" = @{ Kind = "image";    Flag = "-vendor_boot"; Files = @("vendor_boot.img") }
    "init_boot"   = @{ Kind = "image";    Flag = "-init_boot";  Files = @("init_boot.img") }
}

$ShortFlag = @{
    "parameter" = "-p"
    "boot"      = "-b"
    "kernel"    = "-k"
    "system"    = "-s"
    "recovery"  = "-r"
    "misc"      = "-m"
    "uboot"     = "-u"
    "trust"     = "-t"
    "resource"  = "-re"
}

$AliasToName = @{
    "u"           = "uboot"
    "b"           = "boot"
    "k"           = "kernel"
    "s"           = "system"
    "r"           = "recovery"
    "m"           = "misc"
    "t"           = "trust"
    "p"           = "parameter"
    "re"          = "resource"
    "param"       = "parameter"
    "miniloader"  = "loader"
    "spl"         = "loader"
    "firmware"    = "update"
    "fw"          = "update"
}

function Show-Usage {
    Write-Host @"
用法:
  flash.bat [命令|目标...] [选项]
  对应官方手册 tools\upgrade_tool\upgrade_tool_manual.pdf

设备 / 多设备:
  flash.bat ld                   列出全部 Rockusb（Loader / Maskrom）
  flash.bat status               检测连接与模式
  flash.bat maskrom              当前是 Maskrom 才成功
  flash.bat wait-maskrom         等待进入 Maskrom（-Timeout 秒）
  flash.bat -s 244 update        多设备时按 LocationID 选择（手册 1.11）

烧写:
  flash.bat                      烧写 firmware\update.img（或根目录 update.img）
  flash.bat update
  flash.bat boot uboot rootfs    单/多分区
  flash.bat update -EraseFirst   先整片擦除再烧
  flash.bat loader               烧写 MiniLoader（UL）
  flash.bat loader -Storage SPINOR

下载 Boot / 切换:
  flash.bat db                   Maskrom 下载 Boot（不写存储）
  flash.bat rd                   复位设备
  flash.bat to-maskrom           Loader 切到 Maskrom（rd 3）
  flash.bat ssd                  多存储切换（Maskrom 且已 DB）

设备擦除（手册 1.8）:
  flash.bat erase                整片擦除 EF（Maskrom，不需先 DB）
  flash.bat el 0 0x2000          按扇区擦除（仅 eMMC）

读取设备信息（手册 1.9）:
  flash.bat info                 芯片 ID + 存储信息 + 分区表
  flash.bat rci                  芯片 ID
  flash.bat rfi                  存储信息
  flash.bat pl                   分区表

按地址读写（手册 1.7）:
  flash.bat wl 0x12000 oem.img
  flash.bat rl 0x12000 0x2000 out.img

选项:
  -s / -Select <LocationID>   多设备时指定目标
  -Loader <路径>              MiniLoader / 擦除用 loader
  -Storage <EMMC|SPINOR|...>  UL 目标存储
  -EraseFirst                 整包前先 EF
  -NoReset                    烧完不复位
  -SkipConfirm                跳过确认（擦除同样生效）
  -NoDownloadBoot             Maskrom 下不自动 DB
  -RequireMaskrom             非 Maskrom 则退出
  -Timeout <秒>               wait-maskrom 超时，默认 60
"@
}

function Get-RestArgs {
    if (-not $Targets -or $Targets.Count -lt 2) { return @() }
    return @($Targets[1..($Targets.Count - 1)])
}

function Resolve-ExistingFile {
    param([string]$PathHint)
    if ([string]::IsNullOrWhiteSpace($PathHint)) { return $null }
    $candidates = @($PathHint)
    if (-not [System.IO.Path]::IsPathRooted($PathHint)) {
        $candidates += (Join-Path (Get-Location) $PathHint)
        $candidates += (Join-Path $FirmwareDir $PathHint)
        $candidates += (Join-Path $Root $PathHint)
    }
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return $null
}

function Get-PartitionName {
    param([string]$Raw)
    $key = $Raw.Trim().ToLowerInvariant()
    if ($AliasToName.ContainsKey($key)) { $key = $AliasToName[$key] }
    if ($Catalog.Contains($key)) { return $key }
    return $null
}

function Get-PartitionNameFromFile {
    param([string]$FilePath)
    $base = [System.IO.Path]::GetFileNameWithoutExtension($FilePath).ToLowerInvariant()
    $file = [System.IO.Path]::GetFileName($FilePath).ToLowerInvariant()

    if ($file -eq "miniloaderall.bin") { return "loader" }
    if ($file -match "spl_loader" -or $file -match "miniloader" -or $file -match "_loader_") {
        return "loader"
    }

    $name = Get-PartitionName $base
    if ($name) { return $name }

    if ($base -match "^(.*?)[_-](a|b)$") {
        $name = Get-PartitionName $Matches[1]
        if ($name) { return $name }
    }
    return $base
}

function Find-DefaultImage {
    param([string]$PartName)
    $names = New-Object System.Collections.Generic.List[string]
    if ($Catalog.Contains($PartName)) {
        foreach ($n in $Catalog[$PartName].Files) { [void]$names.Add($n) }
    }
    [void]$names.Add("$PartName.img")
    foreach ($dir in @($FirmwareDir, $Root)) {
        foreach ($n in $names) {
            $p = Join-Path $dir $n
            if (Test-Path -LiteralPath $p) {
                return (Resolve-Path -LiteralPath $p).Path
            }
        }
    }
    return $null
}

function Save-LoaderFromUpdate {
    param([string]$UpdatePath)
    if (-not (Test-Path -LiteralPath $UpdatePath)) { return $false }
    $sfi = & {
        Push-Location $ToolDir
        try { & $Tool SFI $UpdatePath 2>&1 | Out-String }
        finally { Pop-Location }
    }
    if ($sfi -notmatch "file=([^\s;]*loader[^\s;]*);.*?offset=(0x[0-9A-Fa-f]+);.*?size=(0x[0-9A-Fa-f]+)") {
        Write-Host "update.img 中未找到 loader 条目，跳过保存。" -ForegroundColor Yellow
        return $false
    }
    $offset = [Convert]::ToInt64($Matches[2].Substring(2), 16)
    $size = [Convert]::ToInt32($Matches[3].Substring(2), 16)
    if ($size -lt 1024 -or $size -gt 8MB) { return $false }
    $fs = [System.IO.File]::OpenRead($UpdatePath)
    try {
        $null = $fs.Seek($offset, [System.IO.SeekOrigin]::Begin)
        $buf = New-Object byte[] $size
        $n = $fs.Read($buf, 0, $size)
        if ($n -ne $size) { return $false }
    } finally {
        $fs.Close()
    }
    if (-not (Test-Path -LiteralPath $FirmwareDir)) {
        New-Item -ItemType Directory -Path $FirmwareDir | Out-Null
    }
    [System.IO.File]::WriteAllBytes($SavedLoader, $buf)
    Write-Host ("已从 update.img 保存 Loader: {0} ({1} 字节)" -f $SavedLoader, $size)

    if ($sfi -match "file=([^\s;]*parameter[^\s;]*);.*?offset=(0x[0-9A-Fa-f]+);.*?size=(0x[0-9A-Fa-f]+)") {
        $poff = [Convert]::ToInt64($Matches[2].Substring(2), 16)
        $psz = [Convert]::ToInt32($Matches[3].Substring(2), 16)
        $pfs = [System.IO.File]::OpenRead($UpdatePath)
        try {
            $null = $pfs.Seek($poff, [System.IO.SeekOrigin]::Begin)
            $pbuf = New-Object byte[] $psz
            $null = $pfs.Read($pbuf, 0, $psz)
        } finally {
            $pfs.Close()
        }
        $text = [System.Text.Encoding]::ASCII.GetString($pbuf)
        $idx = $text.IndexOf("FIRMWARE_VER:")
        if ($idx -ge 0) { $text = $text.Substring($idx) }
        $keep = New-Object System.Collections.Generic.List[string]
        foreach ($line in ($text -split "`r?`n")) {
            $t = $line.Trim()
            if ($t -match '^(FIRMWARE_VER:|TYPE:|CMDLINE:|uuid:)') { [void]$keep.Add($t) }
        }
        if ($keep.Count -gt 0) {
            [System.IO.File]::WriteAllText($SavedParameter, (($keep -join "`n") + "`n"), [System.Text.Encoding]::ASCII)
            Write-Host ("已保存分区表: {0}" -f $SavedParameter)
        }
    }
    return $true
}

function Find-LoaderFile {
    if ($Loader) {
        $resolved = Resolve-ExistingFile $Loader
        if (-not $resolved) { throw "找不到 Loader：$Loader" }
        return $resolved
    }
    if (Test-Path -LiteralPath $SavedLoader) {
        return (Resolve-Path -LiteralPath $SavedLoader).Path
    }
    $fw = Find-DefaultImage "update"
    if ($fw) {
        Write-Host "未找到已保存的 MiniLoaderAll.bin，从 update.img 提取 ..."
        if ((Save-LoaderFromUpdate $fw) -and (Test-Path -LiteralPath $SavedLoader)) {
            return (Resolve-Path -LiteralPath $SavedLoader).Path
        }
    }
    $patterns = @("rk3588_spl_loader*.bin", "*spl_loader*.bin", "*MiniLoader*.bin", "*_loader_*.bin")
    foreach ($dir in @($FirmwareDir, $Root)) {
        foreach ($pat in $patterns) {
            $hit = Get-ChildItem -LiteralPath $dir -Filter $pat -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -ne "update.img" } |
                Select-Object -First 1
            if ($hit) { return $hit.FullName }
        }
    }
    return $null
}

function Find-EraseFile {
    $fromArgs = Get-RestArgs
    if ($fromArgs.Count -ge 1) {
        $resolved = Resolve-ExistingFile $fromArgs[0]
        if ($resolved) { return $resolved }
        throw "找不到擦除用文件：$($fromArgs[0])"
    }
    $loaderPath = Find-LoaderFile
    if ($loaderPath) { return $loaderPath }
    $fw = Find-DefaultImage "update"
    if ($fw) { return $fw }
    throw "擦除需要 MiniLoader 或 update.img。放到 firmware\，或：flash.bat erase <loader|update.img>"
}

function Get-SelectPrefix {
    if ([string]::IsNullOrWhiteSpace($Select)) { return @() }
    return @("-s", "$Select")
}

function Invoke-UpgradeTool {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ToolArgs,
        [switch]$AllowFail
    )
    $all = @()
    $all += Get-SelectPrefix
    $all += $ToolArgs
    Write-Host ("  > upgrade_tool " + ($all -join " ")) -ForegroundColor DarkGray
    Push-Location $ToolDir
    try {
        & $Tool @all
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if (-not $AllowFail -and $code -ne 0) {
        throw "upgrade_tool 失败，退出码 $code"
    }
    return $code
}

function Get-DeviceList {
    $output = & {
        Push-Location $ToolDir
        try { & $Tool LD 2>&1 | Out-String }
        finally { Pop-Location }
    }
    $devices = New-Object System.Collections.Generic.List[object]
    foreach ($line in ($output -split "`r?`n")) {
        $t = $line.Trim()
        if ($t -notmatch "DevNo=") { continue }
        $dev = [pscustomobject]@{
            DevNo      = $null
            Vid        = $null
            UsbPid     = $null
            LocationID = $null
            Mode       = $null
            SerialNo   = $null
            Line       = $t
        }
        if ($t -match "DevNo=(\S+)") { $dev.DevNo = $Matches[1].Trim("`t ,") }
        if ($t -match "Vid=([^\s,]+)") { $dev.Vid = $Matches[1] }
        if ($t -match "Pid=([^\s,]+)") { $dev.UsbPid = $Matches[1] }
        if ($t -match "LocationID=([^\s,]+)") { $dev.LocationID = $Matches[1] }
        if ($t -match "Mode=(\S+)") { $dev.Mode = $Matches[1] }
        if ($t -match "SerialNo=(\S*)") { $dev.SerialNo = $Matches[1] }
        $devices.Add($dev)
    }
    return [pscustomobject]@{
        Devices = @($devices.ToArray())
        Output  = $output
        Found   = ($devices.Count -gt 0)
    }
}

function Select-DeviceFromList {
    param($List)
    if (-not $List.Found) { return $null }
    if ($Select) {
        $hit = @($List.Devices | Where-Object {
            $_.LocationID -eq "$Select" -or $_.DevNo -eq "$Select"
        }) | Select-Object -First 1
        return $hit
    }
    if ($List.Devices.Count -eq 1) { return $List.Devices[0] }
    return $null
}

function Get-DeviceStatus {
    $list = Get-DeviceList
    $chosen = Select-DeviceFromList $list
    $mode = $null
    if ($chosen) { $mode = $chosen.Mode }
    elseif ($list.Devices.Count -eq 1) { $mode = $list.Devices[0].Mode }

    return [pscustomobject]@{
        Found      = [bool]$list.Found
        Mode       = $mode
        Vid        = $(if ($chosen) { $chosen.Vid } else { $null })
        UsbPid     = $(if ($chosen) { $chosen.UsbPid } else { $null })
        DevNo      = $(if ($chosen) { $chosen.DevNo } else { $null })
        LocationID = $(if ($chosen) { $chosen.LocationID } else { $null })
        Selected   = $chosen
        Devices    = $list.Devices
        Multi      = ($list.Devices.Count -gt 1)
        Output     = $list.Output
    }
}

function Get-ModeKind {
    param($Status)
    if (-not $Status.Found) { return "none" }
    $mode = $Status.Mode
    if (-not $mode -and $Status.Multi) { return "multi" }
    if ($mode -match "maskrom") { return "maskrom" }
    if ($mode -match "loader") { return "loader" }
    return "other"
}

function Write-DeviceStatus {
    param($Status)
    Write-Host "========================================"
    Write-Host " Rockchip 设备状态"
    Write-Host "========================================"
    if (-not $Status.Found) {
        Write-Host "连接: 未检测到 Rockusb 设备"
        Write-Host "模式: (无)"
        Write-Host ""
        Write-Host "请确认 USB 已连接，且板子处于 Loader 或 Maskrom。"
        Write-Host $Status.Output
        return
    }

    Write-Host ("设备数: " + @($Status.Devices).Count)
    if ($Select) { Write-Host ("选择 : -s " + $Select) }
    Write-Host ""
    Write-Host ("{0,-6} {1,-12} {2,-10} {3,-10} {4,-10}" -f "DevNo", "LocationID", "Mode", "VID", "PID")
    foreach ($d in $Status.Devices) {
        $mark = ""
        if ($Status.Selected -and $d.LocationID -eq $Status.Selected.LocationID) { $mark = " *" }
        Write-Host ("{0,-6} {1,-12} {2,-10} {3,-10} {4,-10}{5}" -f $d.DevNo, $d.LocationID, $d.Mode, $d.Vid, $d.UsbPid, $mark)
    }

    if ($Status.Multi -and -not $Select) {
        Write-Host ""
        Write-Host ("多设备已连接。后续操作请加 -s <LocationID>，例如：flash.bat -s {0} info" -f $Status.Devices[0].LocationID) -ForegroundColor Yellow
    } elseif ($Status.Selected) {
        $kind = Get-ModeKind $Status
        Write-Host ""
        switch ($kind) {
            "maskrom" { Write-Host "结论: 当前是 Maskrom。" -ForegroundColor Green }
            "loader"  { Write-Host "结论: 当前是 Loader。" -ForegroundColor Green }
            default   { Write-Host ("结论: 模式=" + $Status.Mode) -ForegroundColor Yellow }
        }
    }
    Write-Host ""
    Write-Host $Status.Output
}

function Assert-DeviceReady {
    param([switch]$AllowMulti)
    $st = Get-DeviceStatus
    if (-not $st.Found) {
        throw "未检测到 Rockusb 设备。请让板子进入 Loader 或 Maskrom。"
    }
    if ($st.Multi -and -not $Select -and -not $AllowMulti) {
        Write-DeviceStatus $st
        $sample = $st.Devices[0].LocationID
        throw "检测到 $($st.Devices.Count) 台设备，请用 -s <LocationID> 指定，例如：flash.bat -s $sample <命令>"
    }
    if ($Select -and -not $st.Selected) {
        Write-DeviceStatus $st
        throw "未找到 -s $Select 对应设备。先 flash.bat ld 查看 LocationID。"
    }
    return $st
}

function Confirm-Action {
    param([string]$Prompt)
    if ($SkipConfirm) { return $true }
    $ans = Read-Host $Prompt
    return ($ans -in @("Y", "y"))
}

function Invoke-StatusCommand {
    param([string]$Want)
    $st = Get-DeviceStatus
    Write-DeviceStatus $st
    if ($Select -and $st.Found -and -not $st.Selected) {
        Write-Host "未找到 -s $Select 对应设备。" -ForegroundColor Yellow
        exit 1
    }
    $kind = Get-ModeKind $st
    switch ($Want) {
        "status" {
            if ($st.Found) { exit 0 } else { exit 1 }
        }
        "maskrom" {
            if ($kind -eq "maskrom") { exit 0 }
            if (-not $st.Found) { exit 1 }
            Write-Host "当前不是 Maskrom（实际: $($st.Mode)）。" -ForegroundColor Yellow
            exit 2
        }
        "loader" {
            if ($kind -eq "loader") { exit 0 }
            if (-not $st.Found) { exit 1 }
            Write-Host "当前不是 Loader（实际: $($st.Mode)）。" -ForegroundColor Yellow
            exit 2
        }
    }
}

function Invoke-WaitMaskrom {
    param([int]$Seconds)
    Write-Host "等待 Maskrom，最多 $Seconds 秒 ..."
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $st = Get-DeviceStatus
        if ((Get-ModeKind $st) -eq "maskrom") {
            Write-DeviceStatus $st
            exit 0
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    Write-Host ""
    Write-Host "超时：未进入 Maskrom。" -ForegroundColor Red
    Write-DeviceStatus (Get-DeviceStatus)
    exit 1
}

function Wait-Device {
    param(
        [int]$TimeoutSec = 20,
        [string]$WantMode
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        $st = Get-DeviceStatus
        if ($st.Found -and $st.Selected) {
            if (-not $WantMode -or ($st.Mode -and $st.Mode -ieq $WantMode) -or $st.Mode -ieq "Loader") {
                return $st
            }
        } elseif ($st.Found -and -not $st.Multi) {
            if (-not $WantMode -or ($st.Mode -and $st.Mode -ieq $WantMode) -or $st.Mode -ieq "Loader") {
                return $st
            }
        }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    return (Get-DeviceStatus)
}

function Test-IsMaskrom {
    param($Status)
    return ($Status.Mode -and $Status.Mode -match "maskrom")
}

function Ensure-LoaderMode {
    param($Status)
    if (-not (Test-IsMaskrom $Status)) { return $Status }
    if ($NoDownloadBoot) {
        Write-Host "设备处于 Maskrom，已指定 -NoDownloadBoot，跳过 Download Boot。" -ForegroundColor Yellow
        return $Status
    }
    $loaderPath = Find-LoaderFile
    if (-not $loaderPath) {
        throw @"
设备当前是 Maskrom 模式。进 Maskrom 时已擦除 eMMC 引导区，单分区烧写必须先把 Loader 写入存储 (UL)。
请把 MiniLoaderAll.bin 放到 firmware\（可从 update.img 自动提取），或用 -Loader 指定。
整包烧写 update.img 会自带 loader，不需要这一步。
"@
    }
    Write-Host ""
    Write-Host "设备处于 Maskrom，写入 Loader 到 eMMC (UL) ..."
    Write-Host "Loader: $loaderPath"
    try {
        Invoke-UpgradeTool @("UL", $loaderPath, "-noreset") | Out-Null
    } catch {
        throw "烧写 Loader 失败。请先复位板子再重试。错误：$($_.Exception.Message)"
    }
    Start-Sleep -Seconds 2
    $again = Get-DeviceStatus
    if (-not $again.Found) {
        throw "写入 Loader 之后未再检测到设备，请检查 USB 连接后重试。"
    }
    Write-Host $again.Output
    if (Test-Path -LiteralPath $SavedParameter) {
        Write-Host "写入分区表 (parameter.txt) ..."
        Invoke-UpgradeTool @("DI", "-p", $SavedParameter) | Out-Null
    }
    return $again
}

function New-FlashJob {
    param(
        [string]$PartName,
        [string]$FilePath
    )
    if (-not $PartName) {
        throw "无法识别分区。请用 -Partition 指定，例如：-Partition rootfs `"$FilePath`""
    }
    if (-not $Catalog.Contains($PartName)) {
        return [pscustomobject]@{
            Name = $PartName
            Kind = "image"
            Flag = "-$PartName"
            File = $FilePath
        }
    }
    $entry = $Catalog[$PartName]
    return [pscustomobject]@{
        Name = $PartName
        Kind = $entry.Kind
        Flag = $entry.Flag
        File = $FilePath
    }
}

function Resolve-Jobs {
    $jobs = New-Object System.Collections.Generic.List[object]

    if ($Image) {
        $file = Resolve-ExistingFile $Image
        if (-not $file) { throw "找不到镜像：$Image" }
        if ($Partition) {
            $name = Get-PartitionName $Partition
            if (-not $name) { $name = $Partition.Trim().ToLowerInvariant() }
        } else {
            $name = Get-PartitionNameFromFile $file
        }
        $jobs.Add((New-FlashJob -PartName $name -FilePath $file))
        return $jobs
    }

    if ($Partition -and -not $Targets) {
        $name = Get-PartitionName $Partition
        if (-not $name) { $name = $Partition.Trim().ToLowerInvariant() }
        $file = Find-DefaultImage $name
        if (-not $file) {
            throw "firmware\ 下没有 $name 对应镜像，请用 -Image 指定路径。"
        }
        $jobs.Add((New-FlashJob -PartName $name -FilePath $file))
        return $jobs
    }

    $items = @()
    if ($Targets) {
        foreach ($t in $Targets) {
            $items += ($t -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        }
    }

    if ($items.Count -eq 0) {
        $file = Find-DefaultImage "update"
        if (-not $file) {
            Show-Usage
            throw "未找到 firmware\update.img。请把固件放到 firmware\，或传入镜像路径。"
        }
        $jobs.Add((New-FlashJob -PartName "update" -FilePath $file))
        return $jobs
    }

    foreach ($item in $items) {
        $asFile = Resolve-ExistingFile $item
        if ($asFile) {
            $name = $null
            if ($Partition -and $items.Count -eq 1) {
                $name = Get-PartitionName $Partition
                if (-not $name) { $name = $Partition.Trim().ToLowerInvariant() }
            }
            if (-not $name) { $name = Get-PartitionNameFromFile $asFile }
            $jobs.Add((New-FlashJob -PartName $name -FilePath $asFile))
            continue
        }

        $name = Get-PartitionName $item
        if (-not $name) {
            throw "无法识别目标 `"$item`"。既不是已有文件，也不是已知分区名。运行 flash.bat help 查看用法。"
        }
        $file = Find-DefaultImage $name
        if (-not $file) {
            $expect = ($Catalog[$name].Files -join " / ")
            throw "未找到 $name 镜像。请把 $expect 放到 firmware\，或传入完整路径。"
        }
        $jobs.Add((New-FlashJob -PartName $name -FilePath $file))
    }
    return $jobs
}

function Write-Banner {
    param($Jobs, $Status)
    Write-Host "========================================"
    Write-Host " Rockchip CLI 烧写"
    Write-Host "========================================"
    Write-Host "工具: $Tool"
    if ($Select) { Write-Host ("选择: -s " + $Select) }
    if ($Status.Found -and $Status.Selected) {
        Write-Host ("设备: DevNo={0} LocationID={1} Mode={2}" -f $Status.DevNo, $Status.LocationID, $Status.Mode)
    } elseif ($Status.Found) {
        Write-Host ("设备: 已连接 {0} 台  Mode={1}" -f @($Status.Devices).Count, $Status.Mode)
    } else {
        Write-Host "设备: 未连接"
    }
    Write-Host "任务:"
    foreach ($j in $Jobs) {
        $kindLabel = switch ($j.Kind) {
            "firmware" { "整包 UF" }
            "loader"   { "Loader UL" }
            default    { "分区 DI $($j.Flag)" }
        }
        Write-Host ("  - {0,-10} {1}" -f $kindLabel, $j.File)
    }
    if ($EraseFirst) { Write-Host "选项: 先擦除 (EF)" }
    if ($NoReset) { Write-Host "选项: 烧完不复位" }
    if ($Storage) { Write-Host ("选项: 存储 " + $Storage) }
    Write-Host ""
}

function Invoke-Jobs {
    param($Jobs, $Status)

    $needLoaderMode = $Jobs | Where-Object { $_.Kind -ne "firmware" }
    if ($needLoaderMode) {
        $Status = Ensure-LoaderMode $Status
    }

    $i = 0
    $total = @($Jobs).Count
    foreach ($job in $Jobs) {
        $i++
        Write-Host ""
        Write-Host ("[{0}/{1}] 烧写 {2} ..." -f $i, $total, $job.Name)

        switch ($job.Kind) {
            "firmware" {
                if ($EraseFirst) {
                    Write-Host "先擦除 Flash (EF) ..."
                    Invoke-UpgradeTool @("EF", $job.File) | Out-Null
                }
                $uf = @("UF", $job.File)
                if ($NoReset) { $uf += "-noreset" }
                Invoke-UpgradeTool $uf | Out-Null
                [void](Save-LoaderFromUpdate $job.File)
            }
            "loader" {
                $ul = @("UL", $job.File)
                if ($NoReset) { $ul += "-noreset" }
                if ($Storage) { $ul += $Storage.ToUpperInvariant() }
                Invoke-UpgradeTool $ul | Out-Null
            }
            default {
                try {
                    Invoke-UpgradeTool @("DI", $job.Flag, $job.File) | Out-Null
                } catch {
                    $short = $ShortFlag[$job.Name]
                    if ($short -and $short -ne $job.Flag) {
                        Write-Host "  长参数 $($job.Flag) 失败，改用 $short 重试 ..." -ForegroundColor Yellow
                        Invoke-UpgradeTool @("DI", $short, $job.File) | Out-Null
                    } else {
                        throw
                    }
                }
            }
        }
        Write-Host "  $($job.Name) 完成。" -ForegroundColor Green
    }

    if (-not $NoReset) {
        Write-Host ""
        Write-Host "复位设备 (RD) ..."
        Invoke-UpgradeTool @("RD") -AllowFail | Out-Null
    }
}

function Invoke-DownloadBoot {
    $st = Assert-DeviceReady
    Write-DeviceStatus $st
    $path = $null
    $rest = Get-RestArgs
    if ($rest.Count -ge 1) {
        $path = Resolve-ExistingFile $rest[0]
        if (-not $path) { throw "找不到 Loader：$($rest[0])" }
    } else {
        $path = Find-LoaderFile
    }
    if (-not $path) { throw "未找到 MiniLoader。放到 firmware\ 或：flash.bat db <loader.bin>" }
    Write-Host "Download Boot: $path"
    Invoke-UpgradeTool @("DB", $path) | Out-Null
    Write-Host "完成。" -ForegroundColor Green
}

function Invoke-ResetDevice {
    $st = Assert-DeviceReady
    Write-DeviceStatus $st
    Invoke-UpgradeTool @("RD") | Out-Null
}

function Invoke-ToMaskrom {
    $st = Assert-DeviceReady
    Write-DeviceStatus $st
    if (Test-IsMaskrom $st) {
        Write-Host "已经是 Maskrom，无需切换。"
        return
    }
    if (-not (Confirm-Action "将 Loader 切换到 Maskrom（rd 3）？输入 Y 继续")) {
        Write-Host "已取消。"
        exit 0
    }
    Invoke-UpgradeTool @("RD", "3") | Out-Null
    Write-Host "已发送 rd 3。可用 flash.bat wait-maskrom 等待。"
}

function Invoke-SwitchStorage {
    $st = Assert-DeviceReady
    Write-DeviceStatus $st
    $st = Ensure-LoaderMode $st
    Write-Host "切换存储 (SSD)。带 * 的为当前存储，按提示输入 No。"
    Invoke-UpgradeTool @("SSD") | Out-Null
}

function Invoke-EraseFlash {
    $st = Assert-DeviceReady
    Write-DeviceStatus $st
    $file = Find-EraseFile
    Write-Host "擦除文件: $file"
    Write-Host "手册要求在 Maskrom 下执行 EF，且不必先 DB。"
    if (-not (Test-IsMaskrom $st)) {
        Write-Host ("当前模式是 {0}，不是 Maskrom。" -f $st.Mode) -ForegroundColor Yellow
    }
    if (-not (Confirm-Action "确认整片擦除？此操作会清空存储。输入 Y 继续")) {
        Write-Host "已取消。"
        exit 0
    }
    Invoke-UpgradeTool @("EF", $file) | Out-Null
    Write-Host "擦除完成。" -ForegroundColor Green
}

function Invoke-EraseLba {
    $st = Assert-DeviceReady
    Write-DeviceStatus $st
    $rest = Get-RestArgs
    if ($rest.Count -lt 2) {
        throw "用法: flash.bat el <起始扇区> <扇区数>    例: flash.bat el 0 0x2000"
    }
    $st = Ensure-LoaderMode $st
    Write-Host ("按地址擦除 EL {0} {1}（仅 eMMC）" -f $rest[0], $rest[1])
    if (-not (Confirm-Action "确认按扇区擦除？输入 Y 继续")) {
        Write-Host "已取消。"
        exit 0
    }
    Invoke-UpgradeTool @("EL", $rest[0], $rest[1]) | Out-Null
    Write-Host "擦除完成。" -ForegroundColor Green
}

function Invoke-WriteLba {
    $st = Assert-DeviceReady
    $rest = Get-RestArgs
    if ($rest.Count -lt 2) {
        throw "用法: flash.bat wl <LBA> <文件>    例: flash.bat wl 0x12000 oem.img"
    }
    $file = Resolve-ExistingFile $rest[1]
    if (-not $file) { throw "找不到文件：$($rest[1])" }
    $st = Ensure-LoaderMode $st
    Invoke-UpgradeTool @("WL", $rest[0], $file) | Out-Null
    Write-Host "写入完成。" -ForegroundColor Green
}

function Invoke-ReadLba {
    $st = Assert-DeviceReady
    $rest = Get-RestArgs
    if ($rest.Count -lt 3) {
        throw "用法: flash.bat rl <LBA> <扇区数> <输出文件>    例: flash.bat rl 0x12000 0x2000 out.img"
    }
    $outFile = $rest[2]
    if (-not [System.IO.Path]::IsPathRooted($outFile)) {
        $outFile = Join-Path (Get-Location) $outFile
    }
    $st = Ensure-LoaderMode $st
    Invoke-UpgradeTool @("RL", $rest[0], $rest[1], $outFile) | Out-Null
    Write-Host "已保存: $outFile" -ForegroundColor Green
}

function Invoke-DeviceInfo {
    param([string]$Which)
    $st = Assert-DeviceReady
    Write-DeviceStatus $st

    $runRci = $Which -in @("info", "rci")
    $runRfi = $Which -in @("info", "rfi")
    $runPl  = $Which -in @("info", "pl")

    if ($runRci) {
        Write-Host ""
        Write-Host "[RCI] 芯片 ID ..."
        Invoke-UpgradeTool @("RCI") -AllowFail | Out-Null
    }

    $needLoader = $runRfi -or $runPl
    if ($needLoader) {
        $st = Ensure-LoaderMode $st
    }

    if ($runRfi) {
        Write-Host ""
        Write-Host "[RFI] 存储信息 ..."
        Invoke-UpgradeTool @("RFI") -AllowFail | Out-Null
    }
    if ($runPl) {
        Write-Host ""
        Write-Host "[PL] 分区表 ..."
        Invoke-UpgradeTool @("PL") | Out-Null
    }
}

# ---- main ----
if (-not (Test-Path -LiteralPath $Tool)) {
    throw "找不到 upgrade_tool.exe：$Tool"
}

if ($Storage) {
    $Storage = $Storage.ToUpperInvariant()
    if ($StorageNames -notcontains $Storage) {
        throw "无效 -Storage $Storage。可选: $($StorageNames -join ', ')"
    }
}

$first = $null
if ($Targets -and $Targets.Count -ge 1) { $first = $Targets[0].Trim().ToLowerInvariant() }

if ($Help -or $first -in @("help", "-h", "/h", "-help", "--help", "/?")) {
    Show-Usage
    exit 0
}

try {
    if ($first -in @("status", "mode", "check")) { Invoke-StatusCommand "status" }
    if ($first -in @("maskrom", "is-maskrom", "is_maskrom")) { Invoke-StatusCommand "maskrom" }
    if ($first -in @("is-loader", "is_loader")) { Invoke-StatusCommand "loader" }
    if ($first -in @("wait-maskrom", "wait_maskrom", "waitmaskrom")) { Invoke-WaitMaskrom $Timeout }
    if ($first -in @("ld", "list", "list-device", "dev")) { Invoke-StatusCommand "status" }

    if ($first -in @("info")) { Invoke-DeviceInfo "info"; exit 0 }
    if ($first -in @("rci", "chip", "chipid")) { Invoke-DeviceInfo "rci"; exit 0 }
    if ($first -in @("rfi", "flash-info", "storage-info")) { Invoke-DeviceInfo "rfi"; exit 0 }
    if ($first -in @("pl", "part", "partition", "partitions")) { Invoke-DeviceInfo "pl"; exit 0 }

    if ($first -in @("erase", "ef")) { Invoke-EraseFlash; exit 0 }
    if ($first -in @("el", "erase-lba")) { Invoke-EraseLba; exit 0 }

    if ($first -in @("db", "download-boot")) { Invoke-DownloadBoot; exit 0 }
    if ($first -in @("rd", "reset", "reboot")) { Invoke-ResetDevice; exit 0 }
    if ($first -in @("to-maskrom", "rd3", "switch-maskrom")) { Invoke-ToMaskrom; exit 0 }
    if ($first -in @("ssd", "storage")) { Invoke-SwitchStorage; exit 0 }

    if ($first -in @("wl", "write-lba")) { Invoke-WriteLba; exit 0 }
    if ($first -in @("rl", "read-lba")) { Invoke-ReadLba; exit 0 }

    if ($first -in @("ul")) {
        $rest = Get-RestArgs
        $file = $null
        foreach ($r in $rest) {
            if ($StorageNames -contains $r.ToUpperInvariant()) {
                $Storage = $r.ToUpperInvariant()
            } else {
                $file = Resolve-ExistingFile $r
                if (-not $file) { throw "找不到 Loader：$r" }
            }
        }
        $Targets = @("loader")
        if ($file) { $Image = $file }
        $first = "loader"
    }

    $jobs = Resolve-Jobs
    $st = Assert-DeviceReady
    Write-Banner -Jobs $jobs -Status $st

    if ($RequireMaskrom -and -not (Test-IsMaskrom $st)) {
        Write-Host ("当前不是 Maskrom（实际: " + $st.Mode + "），已指定 -RequireMaskrom，退出。") -ForegroundColor Red
        exit 2
    }
    Write-Host $st.Output

    if (-not (Confirm-Action "确认开始烧写？输入 Y 继续")) {
        Write-Host "已取消。"
        exit 0
    }

    Invoke-Jobs -Jobs $jobs -Status $st
} catch {
    Write-Host ""
    Write-Host "失败：$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "全部完成。" -ForegroundColor Green
exit 0
