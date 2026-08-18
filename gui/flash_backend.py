# -*- coding: utf-8 -*-
"""封装 flash.bat / upgrade_tool 命令行，供 GUI 调用。"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

SECTOR_SIZE = 512

PARTITIONS = [
    ("update", "整包 update.img", "update.img"),
    ("loader", "MiniLoader", "MiniLoaderAll.bin"),
    ("parameter", "parameter", "parameter.txt"),
    ("uboot", "uboot", "uboot.img"),
    ("trust", "trust", "trust.img"),
    ("boot", "boot", "boot.img"),
    ("recovery", "recovery", "recovery.img"),
    ("rootfs", "rootfs", "rootfs.img"),
    ("system", "system", "system.img"),
    ("misc", "misc", "misc.img"),
    ("resource", "resource", "resource.img"),
    ("kernel", "kernel", "kernel.img"),
    ("oem", "oem", "oem.img"),
    ("userdata", "userdata", "userdata.img"),
    ("super", "super", "super.img"),
    ("dtbo", "dtbo", "dtbo.img"),
    ("vbmeta", "vbmeta", "vbmeta.img"),
    ("vendor", "vendor", "vendor.img"),
    ("vendor_boot", "vendor_boot", "vendor_boot.img"),
    ("init_boot", "init_boot", "init_boot.img"),
]

# 分区名 → 默认镜像文件名
DEFAULT_IMAGE_NAMES = {k: fname for k, _label, fname in PARTITIONS}

STORAGE_CHOICES = ("EMMC", "FLASH", "SPINOR", "SPINAND")

MASKROM_GUIDE = """【进入 Maskrom 的常用方式】

一、硬件方式（推荐）
  1. 用 USB 连接板子与电脑
  2. 按住 Recovery / Maskrom 键（以板卡丝印为准）
  3. 上电或短按复位，保持按键约 2~3 秒后松开
  4. 设备管理器出现 Rockusb Device（VID 2207）
  5. 在本工具点「刷新设备」，确认模式为 Maskrom

二、软件方式（设备已在 Loader 模式）
  在本工具点击「切到 Maskrom」，等价命令：
    flash.bat to-maskrom -SkipConfirm
  然后等待设备重新枚举：
    flash.bat wait-maskrom -Timeout 60

三、检查是否已进入
    flash.bat ld
    flash.bat status
    flash.bat maskrom

四、Maskrom 下一键整包示例
    flash.bat update -SkipConfirm
    flash.bat update -EraseFirst -SkipConfirm

五、分区烧写流程
    1. 读取板端分区表（PL）
    2. 为各分区选择镜像并核对大小
    3. 按分区起始 LBA 写入（WL）
"""


@dataclass
class BoardPartition:
    """板端 / parameter 中的一个分区。"""

    name: str
    start_lba: int
    sector_count: Optional[int]  # None = grow / 未知
    grow: bool = False
    source: str = "pl"  # pl | parameter

    @property
    def start_hex(self) -> str:
        return f"0x{self.start_lba:X}"

    @property
    def sectors_hex(self) -> str:
        if self.sector_count is None:
            return "grow"
        return f"0x{self.sector_count:X}"

    @property
    def size_bytes(self) -> Optional[int]:
        if self.sector_count is None:
            return None
        return self.sector_count * SECTOR_SIZE


@dataclass
class SizeCheckResult:
    ok: bool
    warning: bool
    message: str
    image_bytes: int = 0
    part_bytes: Optional[int] = None


def format_bytes(n: Optional[int]) -> str:
    if n is None:
        return "grow/未知"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MB"
    return f"{n / (1024 * 1024 * 1024):.2f} GB"


def parse_int_flex(text: str) -> int:
    t = text.strip().lower().replace(",", "")
    if t.startswith("0x"):
        return int(t, 16)
    return int(t, 10)


def parse_pl_output(text: str) -> List[BoardPartition]:
    """解析 upgrade_tool PL 输出。

    常见行格式：
      01  0x00004000  0x00002000  uboot
      No  LBA         Length      Name
    """
    parts: List[BoardPartition] = []
    seen = set()
    # index + start + length + name
    pat_idx = re.compile(
        r"^\s*(\d+)\s+(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+|-1|0xffffffff)\s+(\S+)",
        re.IGNORECASE,
    )
    # start + length + name（无序号）
    pat_plain = re.compile(
        r"^\s*(0x[0-9A-Fa-f]+)\s+(0x[0-9A-Fa-f]+|-1|0xffffffff)\s+(\S+)$",
        re.IGNORECASE,
    )
    # LBA:xxx Len:xxx Name:xxx
    pat_labeled = re.compile(
        r"LBA\s*[:=]\s*(0x[0-9A-Fa-f]+).*?(?:Len|Size|Length)\s*[:=]\s*(0x[0-9A-Fa-f]+|-1).*?(?:Name|Part)\s*[:=]\s*(\S+)",
        re.IGNORECASE,
    )

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(">"):
            continue
        low = line.lower()
        if "partition" in low and ("info" in low or "list" in low):
            continue
        if re.match(r"^(no\.?|index|lba|name|#)", low):
            continue

        name = start = length = None
        m = pat_idx.match(line)
        if m:
            start, length, name = m.group(2), m.group(3), m.group(4)
        else:
            m = pat_plain.match(line)
            if m:
                start, length, name = m.group(1), m.group(2), m.group(3)
            else:
                m = pat_labeled.search(line)
                if m:
                    start, length, name = m.group(1), m.group(2), m.group(3)

        if not (name and start and length):
            continue

        name = name.strip(" ,;\t\"'")
        # 去掉 name:grow 后缀中的标记
        grow = False
        if ":" in name:
            base, *rest = name.split(":")
            name = base
            grow = any("grow" in r.lower() for r in rest)

        try:
            start_lba = parse_int_flex(start)
        except ValueError:
            continue

        sector_count: Optional[int]
        length_l = length.lower()
        if length_l in ("-1", "0xffffffff", "grow", "-"):
            sector_count = None
            grow = True
        else:
            try:
                sector_count = parse_int_flex(length)
            except ValueError:
                continue
            if sector_count <= 0 or sector_count >= 0xFFFFFFFF:
                sector_count = None
                grow = True

        key = (name.lower(), start_lba)
        if key in seen:
            continue
        seen.add(key)
        parts.append(
            BoardPartition(
                name=name,
                start_lba=start_lba,
                sector_count=sector_count,
                grow=grow,
                source="pl",
            )
        )
    return parts


def parse_parameter_txt(path: Path) -> List[BoardPartition]:
    """从 parameter.txt 的 CMDLINE mtdparts 解析分区。

    条目格式：size@start(name) 或 -@start(name:grow)
    """
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    cmdline = ""
    for line in text.splitlines():
        if line.strip().upper().startswith("CMDLINE:"):
            cmdline = line.split(":", 1)[1].strip()
            break
    if not cmdline:
        return []

    m = re.search(r"mtdparts=[^:]+:(.+)$", cmdline)
    body = m.group(1) if m else cmdline
    # 按逗号切分，但保留括号内
    entries = re.findall(
        r"([^,]+@[^,]+(?:\([^)]+\))?)",
        body,
    )
    if not entries:
        # 简单按逗号
        entries = [e.strip() for e in body.split(",") if e.strip()]

    parts: List[BoardPartition] = []
    for entry in entries:
        entry = entry.strip()
        em = re.match(
            r"^(0x[0-9A-Fa-f]+|-)\s*@\s*(0x[0-9A-Fa-f]+)\s*(?:\(([^)]+)\))?",
            entry,
            re.IGNORECASE,
        )
        if not em:
            continue
        size_s, start_s, name_s = em.group(1), em.group(2), em.group(3) or ""
        grow = False
        name = name_s.strip()
        if ":" in name:
            base, *rest = name.split(":")
            name = base
            grow = any("grow" in r.lower() for r in rest)
        if not name:
            continue
        start_lba = parse_int_flex(start_s)
        if size_s == "-":
            sector_count = None
            grow = True
        else:
            sector_count = parse_int_flex(size_s)
        parts.append(
            BoardPartition(
                name=name,
                start_lba=start_lba,
                sector_count=sector_count,
                grow=grow,
                source="parameter",
            )
        )
    return parts


def check_image_against_partition(image_path: str, part: BoardPartition) -> SizeCheckResult:
    """镜像是否超过分区容量。超出则 warning=True。"""
    p = Path(image_path)
    if not image_path or not p.is_file():
        return SizeCheckResult(ok=False, warning=False, message="未选择镜像或不存在")

    img_size = p.stat().st_size
    if part.grow or part.size_bytes is None:
        return SizeCheckResult(
            ok=True,
            warning=False,
            message=f"镜像 {format_bytes(img_size)}（分区为 grow，不校验上限）",
            image_bytes=img_size,
            part_bytes=None,
        )

    part_bytes = part.size_bytes
    if img_size > part_bytes:
        return SizeCheckResult(
            ok=False,
            warning=True,
            message=(
                f"警告：镜像 {format_bytes(img_size)} 大于分区 "
                f"{format_bytes(part_bytes)}，不能安全烧写"
            ),
            image_bytes=img_size,
            part_bytes=part_bytes,
        )
    return SizeCheckResult(
        ok=True,
        warning=False,
        message=f"镜像 {format_bytes(img_size)} / 分区 {format_bytes(part_bytes)}，可烧写",
        image_bytes=img_size,
        part_bytes=part_bytes,
    )


def find_repo_root(start: Optional[Path] = None) -> Path:
    here = (start or Path(__file__).resolve()).parent
    candidates = [here, here.parent, Path.cwd()]
    for base in candidates:
        for p in [base, *base.parents]:
            if (p / "flash.bat").is_file() and (p / "scripts" / "flash.ps1").is_file():
                return p
    return here.parent if here.name == "gui" else here


class FlashBackend:
    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root) if root else find_repo_root()
        self.flash_bat = self.root / "flash.bat"
        self.firmware_dir = self.root / "firmware"
        self.upgrade_tool = self.root / "tools" / "upgrade_tool" / "upgrade_tool.exe"
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def default_image_path(self, part: str, default_name: str = "") -> str:
        name = default_name or DEFAULT_IMAGE_NAMES.get(part.lower(), f"{part}.img")
        for folder in (self.firmware_dir, self.root):
            path = folder / name
            if path.is_file():
                return str(path)
        # 模糊匹配
        key = part.lower()
        if self.firmware_dir.is_dir():
            for f in self.firmware_dir.iterdir():
                if not f.is_file():
                    continue
                stem = f.stem.lower()
                if stem == key or stem.startswith(key + "_") or stem.startswith(key + "-"):
                    return str(f)
        return str(self.firmware_dir / name)

    def build_args(
        self,
        targets: Sequence[str],
        *,
        select: str = "",
        loader: str = "",
        storage: str = "",
        erase_first: bool = False,
        no_reset: bool = False,
        skip_confirm: bool = True,
        no_download_boot: bool = False,
        require_maskrom: bool = False,
        timeout: Optional[int] = None,
        partition: str = "",
        image: str = "",
    ) -> List[str]:
        args: List[str] = [str(self.flash_bat)]
        args.extend(str(t) for t in targets if t)
        if select.strip():
            args.extend(["-s", select.strip()])
        if loader.strip():
            args.extend(["-Loader", loader.strip()])
        if storage.strip():
            args.extend(["-Storage", storage.strip()])
        if partition.strip():
            args.extend(["-Partition", partition.strip()])
        if image.strip():
            args.extend(["-Image", image.strip()])
        if erase_first:
            args.append("-EraseFirst")
        if no_reset:
            args.append("-NoReset")
        if skip_confirm:
            args.append("-SkipConfirm")
        if no_download_boot:
            args.append("-NoDownloadBoot")
        if require_maskrom:
            args.append("-RequireMaskrom")
        if timeout is not None:
            args.extend(["-Timeout", str(int(timeout))])
        return args

    def format_command(self, args: Sequence[str]) -> str:
        parts = []
        for a in args:
            if " " in a or "\t" in a:
                parts.append(f'"{a}"')
            else:
                parts.append(a)
        return " ".join(parts)

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass

    def _popen_kwargs(self) -> dict:
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return dict(
            cwd=str(self.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )

    def run_capture(self, args: Sequence[str]) -> Tuple[int, str]:
        """同步执行并返回 (exit_code, 全部输出)。"""
        try:
            with self._lock:
                self._proc = subprocess.Popen(list(args), **self._popen_kwargs())
                proc = self._proc
            assert proc.stdout is not None
            out = proc.stdout.read()
            code = proc.wait()
            return code, out or ""
        except Exception as exc:  # noqa: BLE001
            return 1, f"[错误] {exc}"
        finally:
            with self._lock:
                self._proc = None

    def run_async(
        self,
        args: Sequence[str],
        on_line: Callable[[str], None],
        on_done: Callable[[int], None],
    ) -> None:
        def worker() -> None:
            code = 1
            try:
                with self._lock:
                    self._proc = subprocess.Popen(list(args), **self._popen_kwargs())
                    proc = self._proc
                assert proc.stdout is not None
                for line in proc.stdout:
                    on_line(line.rstrip("\r\n"))
                code = proc.wait()
            except Exception as exc:  # noqa: BLE001
                on_line(f"[错误] {exc}")
                code = 1
            finally:
                with self._lock:
                    self._proc = None
                on_done(code)

        threading.Thread(target=worker, daemon=True).start()

    def run_queue_async(
        self,
        jobs: Sequence[Sequence[str]],
        on_line: Callable[[str], None],
        on_done: Callable[[int], None],
    ) -> None:
        """按顺序执行多条命令，任一步失败则停止。"""

        def worker() -> None:
            code = 0
            try:
                for args in jobs:
                    on_line("")
                    on_line(f"$ {self.format_command(args)}")
                    with self._lock:
                        self._proc = subprocess.Popen(list(args), **self._popen_kwargs())
                        proc = self._proc
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        on_line(line.rstrip("\r\n"))
                    code = proc.wait()
                    with self._lock:
                        self._proc = None
                    if code != 0:
                        on_line(f"[中止] 上一步失败，退出码 {code}")
                        break
            except Exception as exc:  # noqa: BLE001
                on_line(f"[错误] {exc}")
                code = 1
            finally:
                with self._lock:
                    self._proc = None
                on_done(code)

        threading.Thread(target=worker, daemon=True).start()

    def fetch_board_partitions(
        self,
        *,
        select: str = "",
        loader: str = "",
        skip_confirm: bool = True,
    ) -> Tuple[List[BoardPartition], str, int]:
        """通过 flash.bat pl 读取板端分区表。"""
        args = self.build_args(
            ["pl"],
            select=select,
            loader=loader,
            skip_confirm=skip_confirm,
        )
        code, out = self.run_capture(args)
        parts = parse_pl_output(out)
        return parts, out, code

    def load_parameter_partitions(self, path: Optional[Path] = None) -> List[BoardPartition]:
        p = path or (self.firmware_dir / "parameter.txt")
        return parse_parameter_txt(p)
