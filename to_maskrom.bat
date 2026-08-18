@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\to_maskrom.ps1" %*
