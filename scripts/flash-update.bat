@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."

set "TOOL=%cd%\tools\upgrade_tool\upgrade_tool.exe"
set "IMG=%~1"
if "%IMG%"=="" set "IMG=%cd%\firmware\update.img"

if not exist "%TOOL%" (
  echo 找不到 upgrade_tool.exe
  exit /b 1
)

echo ========================================
echo  Rockchip CLI 固件升级
echo ========================================
echo 工具: %TOOL%
echo 固件: %IMG%
echo.

if not exist "%IMG%" (
  echo 未找到固件: %IMG%
  echo.
  echo 用法:
  echo   flash-update.bat [update.img路径]
  echo 或把 update.img 放到 firmware\update.img
  exit /b 1
)

echo [1/3] 检测设备 ...
"%TOOL%" LD
if errorlevel 1 (
  echo.
  echo 未检测到 Rockusb 设备。请先安装驱动并使设备进入 Loader/Maskrom。
  exit /b 1
)

echo.
set /p CONFIRM=确认开始烧写？输入 Y 继续: 
if /i not "%CONFIRM%"=="Y" (
  echo 已取消。
  exit /b 0
)

echo.
echo [2/3] 升级固件 UF ...
"%TOOL%" UF "%IMG%"
if errorlevel 1 (
  echo 升级失败。
  exit /b 1
)

echo.
echo 升级完成。
exit /b 0
