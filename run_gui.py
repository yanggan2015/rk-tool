# -*- coding: utf-8 -*-
"""从工程根目录启动烧录 GUI：py run_gui.py"""

from pathlib import Path
import runpy
import sys

gui = Path(__file__).resolve().parent / "gui" / "rk_flash_gui.py"
sys.path.insert(0, str(gui.parent))
runpy.run_path(str(gui), run_name="__main__")
