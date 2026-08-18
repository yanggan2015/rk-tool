#!/bin/bash
# 在 Linux 上远程调用 Windows 的 to_maskrom.bat，再烧写 update.img
# 用法:
#   ./ssh_to_maskrom.sh
#   SSHPASS='你的密码' ./ssh_to_maskrom.sh
set -e

HOST="${HOST:-mypc}"
WIN='C:\code\rk-tool'

ssh_win() {
  if [ -n "${SSHPASS:-}" ]; then
    sshpass -p "$SSHPASS" ssh -o StrictHostKeyChecking=no "$HOST" "$@"
  else
    ssh "$HOST" "$@"
  fi
}

# Windows OpenSSH 默认是 cmd，必须用 cmd /c，且用 && 连接
ssh_win 'cmd.exe /c "cd /d C:\code\rk-tool && to_maskrom.bat"'
ssh_win 'cmd.exe /c "cd /d C:\code\rk-tool && flash.bat -SkipConfirm update"'
