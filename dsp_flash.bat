@echo off
chcp 65001 >nul
setlocal
set "PY="
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PY (
  echo 找不到本机 Python。请安装 Python 3。
  exit /b 1
)
"%PY%" "%~dp0dsp_flash.py" %*
exit /b %ERRORLEVEL%
