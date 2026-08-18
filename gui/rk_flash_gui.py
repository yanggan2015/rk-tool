# -*- coding: utf-8 -*-
"""
瑞芯微 Maskrom 烧录 GUI（选项卡精简版）

启动：
  py run_gui.py
  py gui/rk_flash_gui.py
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

_GUI_DIR = Path(__file__).resolve().parent
if str(_GUI_DIR) not in sys.path:
    sys.path.insert(0, str(_GUI_DIR))

from flash_backend import (  # noqa: E402
    MASKROM_GUIDE,
    STORAGE_CHOICES,
    BoardPartition,
    FlashBackend,
    check_image_against_partition,
    format_bytes,
)


class Theme:
    """亮色：雾白底 + 青玉强调。"""

    BG = "#eef2f6"
    SURFACE = "#ffffff"
    SURFACE2 = "#f4f7fb"
    BORDER = "#d0d8e4"
    TEXT = "#1a2332"
    MUTED = "#6a768a"
    ACCENT = "#0f8f86"
    ACCENT_HOVER = "#0c7a73"
    ACCENT_SOFT = "#e6f7f5"
    WARN = "#d97706"
    DANGER = "#dc4a3d"
    OK = "#1a7f4b"
    INPUT = "#f8fafc"
    FONT = ("Microsoft YaHei UI", 9)
    FONT_BOLD = ("Microsoft YaHei UI", 9, "bold")
    FONT_TITLE = ("Microsoft YaHei UI", 13, "bold")
    FONT_TAB = ("Microsoft YaHei UI", 10, "bold")
    FONT_HINT = ("Microsoft YaHei UI", 8)
    FONT_MONO = ("Consolas", 9)


class RkFlashApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.backend = FlashBackend()
        self.title("RK Flash Tool")
        self.configure(bg=Theme.BG)
        self._apply_window_size()

        self._busy = False
        self._board_parts: List[BoardPartition] = []
        self._row_enabled: Dict[str, tk.BooleanVar] = {}
        self._row_paths: Dict[str, tk.StringVar] = {}
        self._row_status: Dict[str, tk.StringVar] = {}
        self._row_status_lbl: Dict[str, tk.Label] = {}

        self._update_path = tk.StringVar()
        self._loader_path = tk.StringVar()
        self._select = tk.StringVar()
        self._storage = tk.StringVar(value="EMMC")
        self._timeout = tk.StringVar(value="60")
        self._erase_first = tk.BooleanVar(value=False)
        self._no_reset = tk.BooleanVar(value=False)
        self._skip_confirm = tk.BooleanVar(value=True)
        self._no_db = tk.BooleanVar(value=False)
        self._require_maskrom = tk.BooleanVar(value=False)
        self._device_status = tk.StringVar(value="设备：未检测")
        self._part_hint = tk.StringVar(value="尚未读取分区表，请先连接设备并点击「读取板端分区」。")

        self._init_paths()
        self._setup_style()
        self._build_ui()
        self.after(180, self.refresh_device)

    def _apply_window_size(self) -> None:
        """按屏幕工作区自动收窄，保证小屏也能放下。"""
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(780, max(640, sw - 80))
        h = min(540, max(460, sh - 100))
        w = min(w, sw - 40)
        h = min(h, sh - 60)
        self.minsize(min(640, w), min(460, h))
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 2)}")

    def _init_paths(self) -> None:
        self._update_path.set(self.backend.default_image_path("update", "update.img"))
        self._loader_path.set(self.backend.default_image_path("loader", "MiniLoaderAll.bin"))

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", background=Theme.BG, foreground=Theme.TEXT, font=Theme.FONT)
        style.configure("TFrame", background=Theme.BG)
        style.configure("Surf.TFrame", background=Theme.SURFACE)
        style.configure("Surf2.TFrame", background=Theme.SURFACE2)
        style.configure("TLabel", background=Theme.SURFACE, foreground=Theme.TEXT, font=Theme.FONT)
        style.configure("Title.TLabel", background=Theme.BG, foreground=Theme.ACCENT, font=Theme.FONT_TITLE)
        style.configure("Muted.TLabel", background=Theme.SURFACE, foreground=Theme.MUTED, font=Theme.FONT_HINT)
        style.configure("MutedBg.TLabel", background=Theme.BG, foreground=Theme.MUTED, font=Theme.FONT_HINT)
        style.configure("Head.TLabel", background=Theme.SURFACE2, foreground=Theme.MUTED, font=Theme.FONT_HINT)
        style.configure("TCheckbutton", background=Theme.SURFACE, foreground=Theme.TEXT, font=Theme.FONT)
        style.map("TCheckbutton", background=[("active", Theme.SURFACE)])

        style.configure(
            "TEntry",
            fieldbackground=Theme.INPUT,
            foreground=Theme.TEXT,
            insertcolor=Theme.TEXT,
            bordercolor=Theme.BORDER,
            lightcolor=Theme.ACCENT,
            darkcolor=Theme.BORDER,
            padding=3,
        )
        style.configure(
            "TCombobox",
            fieldbackground=Theme.INPUT,
            foreground=Theme.TEXT,
            background=Theme.SURFACE,
            arrowcolor=Theme.TEXT,
            padding=2,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", Theme.INPUT)],
            foreground=[("readonly", Theme.TEXT)],
        )

        style.configure("TNotebook", background=Theme.BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=Theme.SURFACE2,
            foreground=Theme.MUTED,
            padding=(14, 6),
            font=Theme.FONT_TAB,
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", Theme.SURFACE), ("active", Theme.ACCENT_SOFT)],
            foreground=[("selected", Theme.ACCENT), ("active", Theme.TEXT)],
        )

        style.configure(
            "Primary.TButton",
            background=Theme.ACCENT,
            foreground="#ffffff",
            font=Theme.FONT_BOLD,
            padding=(12, 6),
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", Theme.ACCENT_HOVER), ("disabled", Theme.BORDER)],
            foreground=[("disabled", Theme.MUTED)],
        )
        style.configure(
            "Ghost.TButton",
            background=Theme.SURFACE2,
            foreground=Theme.TEXT,
            font=Theme.FONT,
            padding=(8, 4),
            borderwidth=0,
        )
        style.map("Ghost.TButton", background=[("active", Theme.BORDER)])
        style.configure(
            "Warn.TButton",
            background=Theme.WARN,
            foreground="#ffffff",
            font=Theme.FONT_BOLD,
            padding=(8, 4),
            borderwidth=0,
        )
        style.map("Warn.TButton", background=[("active", "#b45309")])
        style.configure(
            "Danger.TButton",
            background=Theme.DANGER,
            foreground="#ffffff",
            font=Theme.FONT_BOLD,
            padding=(8, 4),
            borderwidth=0,
        )
        style.map("Danger.TButton", background=[("active", "#c43d32")])
        style.configure(
            "Vertical.TScrollbar",
            background=Theme.SURFACE2,
            troughcolor=Theme.INPUT,
            arrowcolor=Theme.MUTED,
        )

    # ---------- layout ----------
    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="TFrame")
        root.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)

        head = ttk.Frame(root, style="TFrame")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(head, text="RK Flash Tool", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(head, text="  Maskrom 烧录", style="MutedBg.TLabel").pack(
            side=tk.LEFT, pady=(4, 0)
        )

        status_bar = ttk.Frame(head, style="TFrame")
        status_bar.pack(side=tk.RIGHT)
        status_inner = tk.Frame(status_bar, bg=Theme.ACCENT_SOFT)
        status_inner.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(
            status_inner,
            textvariable=self._device_status,
            bg=Theme.ACCENT_SOFT,
            fg=Theme.ACCENT,
            font=Theme.FONT_BOLD,
            padx=8,
            pady=3,
        ).pack(side=tk.LEFT)
        ttk.Button(status_bar, text="刷新", style="Ghost.TButton", command=self.refresh_device).pack(
            side=tk.LEFT
        )

        nb = ttk.Notebook(root)
        nb.grid(row=1, column=0, sticky="nsew")

        tab_update = ttk.Frame(nb, style="Surf.TFrame")
        tab_parts = ttk.Frame(nb, style="Surf.TFrame")
        tab_cfg = ttk.Frame(nb, style="Surf.TFrame")
        nb.add(tab_update, text="整包烧写")
        nb.add(tab_parts, text="分区烧写")
        nb.add(tab_cfg, text="配置")

        self._build_tab_update(tab_update)
        self._build_tab_parts(tab_parts)
        self._build_tab_config(tab_cfg)

        log_wrap = ttk.Frame(root, style="TFrame")
        log_wrap.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        log_head = ttk.Frame(log_wrap, style="TFrame")
        log_head.pack(fill=tk.X)
        ttk.Label(log_head, text="运行日志", style="MutedBg.TLabel").pack(side=tk.LEFT)
        ttk.Button(log_head, text="清空", style="Ghost.TButton", command=self._clear_log).pack(
            side=tk.RIGHT
        )
        ttk.Button(log_head, text="停止", style="Warn.TButton", command=self.do_stop).pack(
            side=tk.RIGHT, padx=(0, 4)
        )

        log_frame = ttk.Frame(log_wrap, style="Surf.TFrame")
        log_frame.pack(fill=tk.X, pady=(2, 0))
        self.log_text = tk.Text(
            log_frame,
            height=4,
            wrap=tk.WORD,
            bg=Theme.INPUT,
            fg=Theme.OK,
            insertbackground=Theme.TEXT,
            relief=tk.FLAT,
            font=Theme.FONT_MONO,
            padx=6,
            pady=4,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
        )
        sb = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set, state=tk.DISABLED)
        self.log_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _make_scrollable(self, parent: ttk.Frame) -> ttk.Frame:
        """选项卡内可滚动容器，小屏也能滚到全部控件。"""
        wrap = ttk.Frame(parent, style="Surf.TFrame")
        wrap.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(wrap, bg=Theme.SURFACE, highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas, style="Surf.TFrame")
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _sync_scroll(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _sync_width(event: tk.Event) -> None:
            canvas.itemconfigure(win, width=event.width)

        inner.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _sync_width)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _wheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind(_e=None) -> None:
            canvas.bind_all("<MouseWheel>", _wheel)

        def _unbind(_e=None) -> None:
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind)
        canvas.bind("<Leave>", _unbind)
        inner.bind("<Enter>", _bind)
        return inner

    def _pad(self, parent: ttk.Frame) -> ttk.Frame:
        inner = ttk.Frame(parent, style="Surf.TFrame")
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        return inner

    # ===== Tab 1: 整包 =====
    def _build_tab_update(self, parent: ttk.Frame) -> None:
        scroll = self._make_scrollable(parent)
        body = self._pad(scroll)
        ttk.Label(body, text="烧写 update.img 整包固件", style="TLabel").pack(anchor=tk.W)
        ttk.Label(
            body,
            text="设备进入 Maskrom 或 Loader 后，选择镜像并一键烧写。",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(2, 8))

        ttk.Label(body, text="固件路径", style="Muted.TLabel").pack(anchor=tk.W)
        row = ttk.Frame(body, style="Surf.TFrame")
        row.pack(fill=tk.X, pady=(4, 0))
        ttk.Entry(row, textvariable=self._update_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(
            row,
            text="浏览…",
            style="Ghost.TButton",
            command=lambda: self._browse(self._update_path, [("镜像", "*.img"), ("全部", "*.*")]),
        ).pack(side=tk.LEFT)

        opts = ttk.Frame(body, style="Surf.TFrame")
        opts.pack(fill=tk.X, pady=(10, 0))
        ttk.Checkbutton(opts, text="烧写前先整片擦除", variable=self._erase_first).pack(
            side=tk.LEFT, padx=(0, 12)
        )
        ttk.Checkbutton(opts, text="烧完不复位", variable=self._no_reset).pack(side=tk.LEFT)

        hint = ttk.Frame(body, style="Surf2.TFrame")
        hint.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(
            hint,
            text="提示：Maskrom 下 UF 会自动处理 Loader，一般无需再单独烧分区。",
            style="Muted.TLabel",
            wraplength=700,
        ).pack(anchor=tk.W, padx=8, pady=6)

        actions = ttk.Frame(body, style="Surf.TFrame")
        actions.pack(fill=tk.X, pady=(14, 4))
        ttk.Button(
            actions, text="一键烧写整包", style="Primary.TButton", command=self.do_flash_update
        ).pack(side=tk.LEFT)
        ttk.Button(
            actions, text="检测设备", style="Ghost.TButton", command=lambda: self._run_simple(["status"])
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(
            actions, text="切到 Maskrom", style="Warn.TButton", command=self.do_to_maskrom
        ).pack(side=tk.LEFT, padx=(8, 0))

    # ===== Tab 2: 分区（读板端 → 选镜像 → 校验 → 按 LBA 烧） =====
    def _build_tab_parts(self, parent: ttk.Frame) -> None:
        # 分区页：顶部固定工具栏 + 中间可滚列表 + 底部按钮，保证按钮始终可见
        body = ttk.Frame(parent, style="Surf.TFrame")
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(4, weight=1)

        ttk.Label(body, text="按板端分区表烧写", style="TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="读取分区 → 选镜像 → 校验大小 → 按起始 LBA（WL）写入。",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 6))

        tools = ttk.Frame(body, style="Surf.TFrame")
        tools.grid(row=2, column=0, sticky="ew")
        ttk.Button(
            tools, text="读取板端分区", style="Primary.TButton", command=self.do_fetch_partitions
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            tools, text="parameter.txt", style="Ghost.TButton", command=self.do_load_parameter
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(tools, text="全选有镜像", style="Ghost.TButton", command=self._select_with_images).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(tools, text="清空", style="Ghost.TButton", command=self._clear_part_checks).pack(
            side=tk.LEFT
        )

        ttk.Label(body, textvariable=self._part_hint, style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(6, 2)
        )

        list_box = ttk.Frame(body, style="Surf.TFrame")
        list_box.grid(row=4, column=0, sticky="nsew", pady=(2, 0))

        header = ttk.Frame(list_box, style="Surf2.TFrame")
        header.pack(fill=tk.X)
        for text, w in [
            ("烧", 3),
            ("分区", 8),
            ("起始", 10),
            ("扇区", 8),
            ("容量", 8),
            ("镜像", 18),
            ("校验", 16),
        ]:
            ttk.Label(header, text=text, style="Head.TLabel", width=w).pack(
                side=tk.LEFT, padx=2, pady=3
            )

        list_wrap = ttk.Frame(list_box, style="Surf.TFrame")
        list_wrap.pack(fill=tk.BOTH, expand=True)
        # 同时支持纵向 + 横向滚动，避免控件被裁切
        self._part_canvas = tk.Canvas(list_wrap, bg=Theme.SURFACE, highlightthickness=0)
        vsb = ttk.Scrollbar(list_wrap, orient=tk.VERTICAL, command=self._part_canvas.yview)
        hsb = ttk.Scrollbar(list_wrap, orient=tk.HORIZONTAL, command=self._part_canvas.xview)
        self._part_inner = ttk.Frame(self._part_canvas, style="Surf.TFrame")
        self._part_win = self._part_canvas.create_window((0, 0), window=self._part_inner, anchor="nw")

        self._part_inner.bind(
            "<Configure>",
            lambda _e: self._part_canvas.configure(scrollregion=self._part_canvas.bbox("all")),
        )
        self._part_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._part_canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        list_wrap.rowconfigure(0, weight=1)
        list_wrap.columnconfigure(0, weight=1)

        def _wheel(event: tk.Event) -> None:
            self._part_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._part_canvas.bind("<Enter>", lambda _e: self._part_canvas.bind_all("<MouseWheel>", _wheel))
        self._part_canvas.bind("<Leave>", lambda _e: self._part_canvas.unbind_all("<MouseWheel>"))

        self._empty_lbl = ttk.Label(self._part_inner, text="分区列表为空", style="Muted.TLabel")
        self._empty_lbl.pack(pady=20)

        actions = ttk.Frame(body, style="Surf.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(
            actions, text="按地址烧写已选分区", style="Primary.TButton", command=self.do_flash_parts
        ).pack(side=tk.LEFT)
        ttk.Button(
            actions, text="只烧 Loader", style="Ghost.TButton", command=self.do_flash_loader
        ).pack(side=tk.LEFT, padx=(8, 0))

    def _clear_part_rows(self) -> None:
        for child in self._part_inner.winfo_children():
            child.destroy()
        self._row_enabled.clear()
        self._row_paths.clear()
        self._row_status.clear()
        self._row_status_lbl.clear()

    def _render_partitions(self, parts: List[BoardPartition], source_label: str) -> None:
        self._board_parts = parts
        self._clear_part_rows()
        if not parts:
            self._empty_lbl = ttk.Label(self._part_inner, text="未解析到分区", style="Muted.TLabel")
            self._empty_lbl.pack(pady=40)
            self._part_hint.set(f"{source_label}：0 个分区")
            return

        self._part_hint.set(f"{source_label}：共 {len(parts)} 个分区（扇区=512 字节）")

        for part in parts:
            key = f"{part.name}@{part.start_hex}"
            en = tk.BooleanVar(value=False)
            path_var = tk.StringVar(value=self.backend.default_image_path(part.name))
            status_var = tk.StringVar(value="未选镜像")
            self._row_enabled[key] = en
            self._row_paths[key] = path_var
            self._row_status[key] = status_var

            row = ttk.Frame(self._part_inner, style="Surf.TFrame")
            row.pack(fill=tk.X, pady=2)

            ttk.Checkbutton(row, variable=en, width=3).pack(side=tk.LEFT, padx=1)
            ttk.Label(row, text=part.name, width=8).pack(side=tk.LEFT, padx=1)
            ttk.Label(row, text=part.start_hex, width=10, style="Muted.TLabel").pack(
                side=tk.LEFT, padx=1
            )
            ttk.Label(row, text=part.sectors_hex, width=8, style="Muted.TLabel").pack(
                side=tk.LEFT, padx=1
            )
            ttk.Label(row, text=format_bytes(part.size_bytes), width=8, style="Muted.TLabel").pack(
                side=tk.LEFT, padx=1
            )
            ttk.Entry(row, textvariable=path_var, width=18).pack(side=tk.LEFT, padx=2)
            ttk.Button(
                row,
                text="…",
                width=3,
                style="Ghost.TButton",
                command=lambda k=key, p=part: self._browse_part_image(k, p),
            ).pack(side=tk.LEFT)

            st_lbl = tk.Label(
                row,
                textvariable=status_var,
                bg=Theme.SURFACE,
                fg=Theme.MUTED,
                font=Theme.FONT_HINT,
                width=18,
                anchor="w",
            )
            st_lbl.pack(side=tk.LEFT, padx=4)
            self._row_status_lbl[key] = st_lbl

            # 若默认路径存在则自动勾选并校验
            if Path(path_var.get()).is_file():
                en.set(True)
            self._refresh_row_check(key, part)

            path_var.trace_add(
                "write",
                lambda *_a, k=key, p=part: self._refresh_row_check(k, p),
            )

    def _browse_part_image(self, key: str, part: BoardPartition) -> None:
        var = self._row_paths[key]
        self._browse(var, [("镜像", "*.img *.bin"), ("全部", "*.*")])
        if var.get() and Path(var.get()).is_file():
            self._row_enabled[key].set(True)
        self._refresh_row_check(key, part)

    def _refresh_row_check(self, key: str, part: BoardPartition) -> None:
        path = self._row_paths[key].get().strip()
        result = check_image_against_partition(path, part)
        self._row_status[key].set(result.message)
        lbl = self._row_status_lbl.get(key)
        if not lbl:
            return
        if result.warning:
            lbl.configure(fg=Theme.DANGER)
            # 超限时取消勾选，避免误烧
            self._row_enabled[key].set(False)
            self._log(f"[警告] {part.name}: {result.message}")
        elif result.ok and path and Path(path).is_file():
            lbl.configure(fg=Theme.OK)
        else:
            lbl.configure(fg=Theme.MUTED)

    def _part_by_key(self, key: str) -> Optional[BoardPartition]:
        for p in self._board_parts:
            if f"{p.name}@{p.start_hex}" == key:
                return p
        return None

    def _select_with_images(self) -> None:
        for key, en in self._row_enabled.items():
            path = self._row_paths[key].get()
            part = self._part_by_key(key)
            if not part:
                continue
            result = check_image_against_partition(path, part)
            en.set(bool(result.ok and Path(path).is_file() and not result.warning))
            self._refresh_row_check(key, part)

    def _clear_part_checks(self) -> None:
        for en in self._row_enabled.values():
            en.set(False)

    def do_fetch_partitions(self) -> None:
        if self._busy:
            messagebox.showinfo("忙碌中", "已有任务在执行。")
            return
        self._busy = True
        self._part_hint.set("正在读取板端分区表（PL）…")
        self._log("")
        self._log("读取板端分区表…")

        def worker() -> None:
            kw = self._common_kwargs()
            parts, out, code = self.backend.fetch_board_partitions(
                select=kw["select"],
                loader=kw["loader"],
                skip_confirm=kw["skip_confirm"],
            )

            def finish() -> None:
                self._busy = False
                for line in out.splitlines():
                    if line.strip():
                        self._log(line)
                if parts:
                    self._render_partitions(parts, "板端 PL")
                    self._log(f"[成功] 解析到 {len(parts)} 个分区")
                else:
                    self._part_hint.set(
                        "未能从设备解析分区。可确认设备已连接，或改用「从 parameter.txt 加载」。"
                    )
                    messagebox.showwarning(
                        "未读到分区",
                        "未能解析板端分区表。\n请确认设备在 Loader/Maskrom，"
                        "或使用 parameter.txt 作为备选。",
                    )
                    self._log(f"[结束] 退出码 {code}，未解析到分区行")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def do_load_parameter(self) -> None:
        path = self.backend.firmware_dir / "parameter.txt"
        if not path.is_file():
            chosen = filedialog.askopenfilename(
                title="选择 parameter.txt",
                filetypes=[("parameter", "*.txt"), ("全部", "*.*")],
            )
            if not chosen:
                return
            path = Path(chosen)
        parts = self.backend.load_parameter_partitions(path)
        if not parts:
            messagebox.showwarning("解析失败", f"无法从中解析分区：\n{path}")
            return
        self._render_partitions(parts, f"parameter ({path.name})")
        self._log(f"[提示] 已从 {path} 加载 {len(parts)} 个分区（非实时板端）")

    # ===== Tab 3: 配置 =====
    def _build_tab_config(self, parent: ttk.Frame) -> None:
        scroll = self._make_scrollable(parent)
        body = self._pad(scroll)

        ttk.Label(body, text="设备与烧写选项", style="TLabel").pack(anchor=tk.W)
        ttk.Label(
            body, text="多设备时填写 LocationID；其余为 flash.bat 全局开关。", style="Muted.TLabel"
        ).pack(anchor=tk.W, pady=(2, 8))

        form = ttk.Frame(body, style="Surf.TFrame")
        form.pack(fill=tk.X)
        row1 = ttk.Frame(form, style="Surf.TFrame")
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="LocationID", style="Muted.TLabel", width=14).pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self._select, width=14).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row1, text="Storage", style="Muted.TLabel").pack(side=tk.LEFT)
        ttk.Combobox(
            row1, textvariable=self._storage, values=STORAGE_CHOICES, width=10, state="readonly"
        ).pack(side=tk.LEFT, padx=4)
        ttk.Label(row1, text="超时(秒)", style="Muted.TLabel").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Entry(row1, textvariable=self._timeout, width=6).pack(side=tk.LEFT, padx=4)

        ttk.Label(form, text="MiniLoader 路径", style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 2))
        lr = ttk.Frame(form, style="Surf.TFrame")
        lr.pack(fill=tk.X)
        ttk.Entry(lr, textvariable=self._loader_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6)
        )
        ttk.Button(
            lr,
            text="浏览…",
            style="Ghost.TButton",
            command=lambda: self._browse(self._loader_path, [("Loader", "*.bin"), ("全部", "*.*")]),
        ).pack(side=tk.LEFT)

        flags = ttk.Frame(body, style="Surf.TFrame")
        flags.pack(fill=tk.X, pady=(10, 0))
        for text, var in [
            ("跳过确认 (-SkipConfirm)", self._skip_confirm),
            ("要求 Maskrom (-RequireMaskrom)", self._require_maskrom),
            ("不自动 UL (-NoDownloadBoot)", self._no_db),
        ]:
            ttk.Checkbutton(flags, text=text, variable=var).pack(side=tk.LEFT, padx=(0, 10))

        dev_btns = ttk.Frame(body, style="Surf.TFrame")
        dev_btns.pack(fill=tk.X, pady=(10, 0))
        for text, cmd in [
            ("列出设备", lambda: self._run_simple(["ld"])),
            ("设备信息", lambda: self._run_simple(["info"])),
            ("复位", self.do_rd),
            ("Download Boot", self.do_db),
            ("整片擦除", self.do_erase),
        ]:
            style = "Danger.TButton" if text == "整片擦除" else "Ghost.TButton"
            ttk.Button(dev_btns, text=text, style=style, command=cmd).pack(
                side=tk.LEFT, padx=(0, 4), pady=(0, 4)
            )

        ttk.Label(body, text="进入 Maskrom · 指令", style="TLabel").pack(anchor=tk.W, pady=(12, 0))
        ttk.Label(
            body, text="可编辑；可填入标准步骤或复制。", style="Muted.TLabel"
        ).pack(anchor=tk.W, pady=(2, 4))

        bar = ttk.Frame(body, style="Surf.TFrame")
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="标准指引", style="Ghost.TButton", command=self._fill_guide).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(bar, text="复制", style="Ghost.TButton", command=self._copy_guide).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(bar, text="切到 Maskrom", style="Warn.TButton", command=self.do_to_maskrom).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(
            bar, text="等待 Maskrom", style="Ghost.TButton", command=self.do_wait_maskrom
        ).pack(side=tk.LEFT)

        self.guide_text = tk.Text(
            body,
            wrap=tk.WORD,
            height=10,
            bg=Theme.INPUT,
            fg=Theme.TEXT,
            insertbackground=Theme.TEXT,
            relief=tk.FLAT,
            font=Theme.FONT_MONO,
            padx=6,
            pady=4,
            highlightthickness=1,
            highlightbackground=Theme.BORDER,
            highlightcolor=Theme.ACCENT,
        )
        self.guide_text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self._fill_guide()

        ttk.Label(body, text=f"工程目录：{self.backend.root}", style="Muted.TLabel").pack(
            anchor=tk.W, pady=(8, 4)
        )

    def _form_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, width: int = 20) -> None:
        ttk.Label(parent, text=label, style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 4))
        ttk.Entry(parent, textvariable=var, width=width).pack(anchor=tk.W)

    def _form_row_combo(
        self, parent: ttk.Frame, label: str, var: tk.StringVar, values: Tuple[str, ...]
    ) -> None:
        ttk.Label(parent, text=label, style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 4))
        ttk.Combobox(parent, textvariable=var, values=values, width=12, state="readonly").pack(
            anchor=tk.W
        )

    # ---------- helpers ----------
    def _browse(self, var: tk.StringVar, filetypes: List[Tuple[str, str]]) -> None:
        initial = var.get()
        init_dir = str(Path(initial).parent) if initial else str(self.backend.firmware_dir)
        path = filedialog.askopenfilename(initialdir=init_dir, filetypes=filetypes)
        if path:
            var.set(path)

    def _fill_guide(self) -> None:
        self.guide_text.delete("1.0", tk.END)
        self.guide_text.insert("1.0", MASKROM_GUIDE)

    def _copy_guide(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.guide_text.get("1.0", tk.END).strip())
        self._log("[提示] 已复制 Maskrom 指引")

    def _common_kwargs(self) -> dict:
        raw = self._timeout.get().strip()
        timeout = int(raw) if raw.isdigit() else 60
        return dict(
            select=self._select.get(),
            loader=self._loader_path.get(),
            storage=self._storage.get(),
            erase_first=self._erase_first.get(),
            no_reset=self._no_reset.get(),
            skip_confirm=self._skip_confirm.get(),
            no_download_boot=self._no_db.get(),
            require_maskrom=self._require_maskrom.get(),
            timeout=timeout,
        )

    def _log(self, line: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _run(self, args: List[str], *, confirm: Optional[str] = None) -> None:
        if self._busy:
            messagebox.showinfo("忙碌中", "已有任务在执行，请等待或点「停止」。")
            return
        if confirm and not messagebox.askyesno("确认", confirm):
            return
        self._log("")
        self._log(f"$ {self.backend.format_command(args)}")
        self._busy = True

        def on_line(line: str) -> None:
            self.after(0, lambda: self._log(line))

        def on_done(code: int) -> None:
            def finish() -> None:
                self._busy = False
                self._log(f"[结束] 退出码 {code}（{'成功' if code == 0 else '失败'}）")
                if code == 0:
                    self.refresh_device()

            self.after(0, finish)

        self.backend.run_async(args, on_line, on_done)

    def _run_queue(self, jobs: List[List[str]], *, confirm: Optional[str] = None) -> None:
        if self._busy:
            messagebox.showinfo("忙碌中", "已有任务在执行，请等待或点「停止」。")
            return
        if not jobs:
            return
        if confirm and not messagebox.askyesno("确认", confirm):
            return
        self._busy = True

        def on_line(line: str) -> None:
            self.after(0, lambda: self._log(line))

        def on_done(code: int) -> None:
            def finish() -> None:
                self._busy = False
                self._log(f"[结束] 退出码 {code}（{'成功' if code == 0 else '失败'}）")
                if code == 0:
                    self.refresh_device()

            self.after(0, finish)

        self.backend.run_queue_async(jobs, on_line, on_done)

    def _run_simple(self, targets: List[str]) -> None:
        kw = self._common_kwargs()
        if targets[0] in ("ld", "status", "maskrom", "info", "rci", "rfi", "pl"):
            kw["erase_first"] = False
        self._run(self.backend.build_args(targets, **kw))

    # ---------- actions ----------
    def refresh_device(self) -> None:
        args = self.backend.build_args(["status"], select=self._select.get(), skip_confirm=True)
        lines: List[str] = []

        def on_line(line: str) -> None:
            lines.append(line)
            self.after(0, lambda: self._log(line))

        def on_done(code: int) -> None:
            text = " | ".join(x.strip() for x in lines if x.strip())
            if not text:
                text = "未检测到 Rockusb 设备" if code else "已连接"
            if len(text) > 48:
                text = text[:45] + "..."
            self.after(0, lambda: self._device_status.set(f"设备：{text}"))

        if not self._busy:
            self._log("$ " + self.backend.format_command(args))
            self.backend.run_async(args, on_line, on_done)

    def do_flash_update(self) -> None:
        img = self._update_path.get().strip()
        if not img or not Path(img).is_file():
            messagebox.showwarning("缺少镜像", "请选择有效的 update.img")
            return
        args = self.backend.build_args([img], **self._common_kwargs())
        self._run(args, confirm=f"确认整包烧写？\n{img}")

    def do_flash_parts(self) -> None:
        if not self._board_parts:
            messagebox.showwarning("无分区表", "请先「读取板端分区」或加载 parameter.txt")
            return

        jobs: List[List[str]] = []
        summary: List[str] = []
        warnings: List[str] = []

        for key, en in self._row_enabled.items():
            if not en.get():
                continue
            part = self._part_by_key(key)
            if not part:
                continue
            path = self._row_paths[key].get().strip()
            result = check_image_against_partition(path, part)
            if result.warning:
                warnings.append(f"{part.name}: {result.message}")
                continue
            if not result.ok:
                messagebox.showwarning("镜像无效", f"{part.name}: {result.message}")
                return
            # 按分区起始地址 WL 写入
            kw = self._common_kwargs()
            # 多分区连续烧写时中间不复位，最后一条再按选项复位
            kw["no_reset"] = True
            args = self.backend.build_args(["wl", part.start_hex, path], **kw)
            jobs.append(args)
            summary.append(
                f"{part.name} @ {part.start_hex} ← {Path(path).name} "
                f"({format_bytes(result.image_bytes)} / {format_bytes(part.size_bytes)})"
            )

        if warnings:
            messagebox.showwarning(
                "镜像超过分区",
                "以下分区镜像过大，已跳过：\n\n" + "\n".join(warnings),
            )
        if not jobs:
            messagebox.showwarning("无可烧写项", "请勾选已选镜像且未超限的分区")
            return

        # 最后一条按用户 NoReset 选项；若需要复位则追加 rd
        if not self._no_reset.get():
            jobs.append(self.backend.build_args(["rd"], **self._common_kwargs()))

        confirm = "将按 LBA 地址依次烧写：\n\n" + "\n".join(summary)
        self._run_queue(jobs, confirm=confirm)

    def do_flash_loader(self) -> None:
        path = self._loader_path.get().strip()
        if not path or not Path(path).is_file():
            messagebox.showwarning("缺少 Loader", "请在配置页指定 MiniLoader")
            return
        args = self.backend.build_args(["ul", path], **self._common_kwargs())
        self._run(args, confirm=f"确认写入 Loader？\n{path}")

    def do_to_maskrom(self) -> None:
        args = self.backend.build_args(["to-maskrom"], **self._common_kwargs())
        self._run(args, confirm="确认将设备切换到 Maskrom？（RD 3）")

    def do_wait_maskrom(self) -> None:
        self._run(self.backend.build_args(["wait-maskrom"], **self._common_kwargs()))

    def do_db(self) -> None:
        path = self._loader_path.get().strip()
        targets = ["db", path] if path else ["db"]
        self._run(self.backend.build_args(targets, **self._common_kwargs()))

    def do_rd(self) -> None:
        self._run(self.backend.build_args(["rd"], **self._common_kwargs()))

    def do_erase(self) -> None:
        args = self.backend.build_args(["erase"], **self._common_kwargs())
        self._run(args, confirm="整片擦除不可恢复，通常需要 Maskrom。\n确认继续？")

    def do_stop(self) -> None:
        self.backend.stop()
        self._busy = False
        self._log("[提示] 已发送停止信号")


def main() -> None:
    app = RkFlashApp()
    app.mainloop()


if __name__ == "__main__":
    main()
