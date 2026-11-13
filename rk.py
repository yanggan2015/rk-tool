#!/usr/bin/env python3
"""Rockchip 烧写（精简）

用法:
  rk.py ld                         列设备
  rk.py db [-b BOARD]              Maskrom Download Boot
  rk.py ul [-b BOARD]              写入 Loader 到存储
  rk.py uf <update.img>            整包烧写
  rk.py di <分区> <镜像> [-b BOARD] 单分区烧写（Maskrom 自动 DB）
  rk.py boards                     列出 firmware 下板子 loader
  rk.py rd                         复位
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FW = ROOT / "firmware"
TOOL = ROOT / "tools" / "upgrade_tool" / "upgrade_tool.exe"

PID_BOARD = {
    "0x350a": "ok3568",  # RK3568
    "0x350b": "tl3588",  # RK3588
    "0x350d": "ok3562",  # RK3562
}

BOARD_CHIP = {
    "ok3568": "3568",
    "rk3568": "3568",
    "ok3562": "3562",
    "ok3588": "3588",
    "tl3588": "3588",
    "opt3588": "3588",
}


def die(msg: str, code: int = 1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def tool(args, check=True):
    if not TOOL.is_file():
        die(f"找不到 upgrade_tool: {TOOL}")
    print(">", " ".join(str(c) for c in [TOOL.name, *args]))
    p = subprocess.run([str(TOOL), *args], cwd=TOOL.parent)
    if check and p.returncode:
        die(f"失败 ({p.returncode})")
    return p.returncode


def list_devices():
    p = subprocess.run(
        [str(TOOL), "LD"],
        cwd=TOOL.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    text = (p.stdout or "") + (p.stderr or "")
    print(text.strip())
    devs = []
    for m in re.finditer(
        r"DevNo=(\d+)\s+Vid=(\S+),Pid=(\S+),LocationID=(\d+)\s+Mode=(\S+)",
        text,
    ):
        devs.append(
            {
                "pid": m.group(3).lower(),
                "loc": m.group(4),
                "mode": m.group(5),
            }
        )
    return devs


def pick_board(explicit: str | None) -> str:
    if explicit:
        return explicit
    devs = list_devices()
    if not devs:
        die("未检测到 Rockusb 设备")
    pid = devs[0]["pid"]
    board = PID_BOARD.get(pid)
    if not board:
        die(f"未知 PID {pid}，请 -b 指定。可用: {', '.join(BOARD_CHIP)}")
    print(f"自动板型: {board} (PID {pid})")
    return board


def loader_path(board: str) -> Path:
    p = FW / board / "MiniLoaderAll.bin"
    if not p.is_file():
        die(f"找不到 loader: {p}")
    return p


def ensure_db(board: str, sel: list):
    devs = list_devices()
    if not devs:
        die("未检测到设备")
    if devs[0]["mode"].lower() != "maskrom":
        return
    ld = loader_path(board)
    print(f"Maskrom -> DB {ld}")
    tool([*sel, "DB", str(ld)])


def cmd_boards():
    for d in sorted(p for p in FW.iterdir() if p.is_dir()):
        ld = d / "MiniLoaderAll.bin"
        if not ld.is_file():
            continue
        chip = BOARD_CHIP.get(d.name, "?")
        print(f"{d.name:12} chip={chip}  {ld.stat().st_size} bytes")


def main():
    ap = argparse.ArgumentParser(description="Rockchip 烧写")
    ap.add_argument("cmd", help="ld|db|ul|uf|di|boards|rd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("-b", "--board", help="板型，如 ok3568 / tl3588")
    ap.add_argument("-s", "--select", help="LocationID")
    ns = ap.parse_args()
    sel = ["-s", ns.select] if ns.select else []
    c = ns.cmd.lower()

    if c == "boards":
        cmd_boards()
    elif c == "ld":
        list_devices()
    elif c == "rd":
        tool([*sel, "RD"])
    elif c == "db":
        board = pick_board(ns.board)
        tool([*sel, "DB", str(loader_path(board))])
    elif c == "ul":
        board = pick_board(ns.board)
        ensure_db(board, sel)
        tool([*sel, "UL", str(loader_path(board))])
    elif c == "uf":
        if not ns.args:
            die("用法: rk.py uf <update.img>")
        img = Path(ns.args[0])
        if not img.is_file():
            die(f"找不到: {img}")
        tool([*sel, "UF", str(img.resolve())])
        tool([*sel, "RD"], check=False)
    elif c == "di":
        if len(ns.args) < 2:
            die("用法: rk.py di <分区> <镜像>")
        img = Path(ns.args[1])
        if not img.is_file():
            die(f"找不到: {img}")
        board = pick_board(ns.board)
        ensure_db(board, sel)
        part = ns.args[0]
        flag = part if part.startswith("-") else f"-{part}"
        tool([*sel, "DI", flag, str(img.resolve())])
        tool([*sel, "RD"], check=False)
    else:
        die(f"未知命令: {ns.cmd}")


if __name__ == "__main__":
    main()
