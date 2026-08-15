@echo off
chcp 65001 >nul
cd /d "%~dp0.."
"tools\upgrade_tool\upgrade_tool.exe" %*
