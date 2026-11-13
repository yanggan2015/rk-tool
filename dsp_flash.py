#!/usr/bin/env python3
"""
dsp_flash.py — 下载 DSP 项目最新 update.img 并烧写到板子

封装:
  dsp_download.py   拉镜像
  flash.bat         烧写

用法:
  python dsp_flash.py -l
  python dsp_flash.py -u opt-opt_tl3588
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import dsp_download as dd  # noqa: E402


def cmd_list():
    for p in dd.list_projects():
        print(p)


def download_latest_update(project, out_dir):
    versions = dd.list_versions(project)
    if not versions:
        sys.exit(f"项目 '{project}' 不存在或无版本目录")
    version = dd.pick_latest(versions)
    images = dd.list_images(project, version)
    matches = dd.match_images(images, "update.img")
    if not matches:
        sys.exit(
            f"在 {project}/{version} 中未找到 update.img。\n"
            f"可用镜像:\n  " + "\n  ".join(sorted(images))
        )
    if len(matches) > 1:
        sys.exit(
            "匹配到多个 update.img，请先用 dsp_download.py -l -p "
            f"{project} 确认:\n  " + "\n  ".join(matches)
        )

    name = matches[0]
    url = f"{dd.BASE_URL}/{project}/{version}/{name}"
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, name)
    dest = os.path.join(out_dir, "update.img")

    print(f"项目: {project}")
    print(f"版本: {version}  (最新)")
    print(f"下载 {url}")
    print(f"  -> {dest}")

    with dd.requests.get(url, headers=dd.UA, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    dd._progress(done, total)
    print(f"\n下载完成: {tmp}  ({done / 1e6:.1f} MB)")

    if os.path.abspath(tmp) != os.path.abspath(dest):
        if os.path.exists(dest):
            os.remove(dest)
        os.replace(tmp, dest)
    print(f"已放到: {dest}")
    return dest


def flash_update(image):
    bat = os.path.join(ROOT, "flash.bat")
    if not os.path.isfile(bat):
        sys.exit(f"找不到 {bat}")
    print(f"烧写: {image}")
    # Windows: flash.bat -> scripts\flash.ps1
    cmd = ["cmd", "/c", bat, "-SkipConfirm", image]
    print("  > " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        sys.exit(r.returncode)
    print("烧写完成。")


def main():
    ap = argparse.ArgumentParser(
        prog="dsp_flash.py",
        description="列出 DSP 项目，或下载最新 update.img 并烧写到板子。",
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("-l", "--list", action="store_true", help="列出所有项目")
    g.add_argument(
        "-u",
        metavar="PROJECT",
        help="下载该项目最新 update.img 到工程目录并烧写",
    )
    args = ap.parse_args()

    if args.list:
        cmd_list()
        return

    dest = download_latest_update(args.u, ROOT)
    flash_update(dest)


if __name__ == "__main__":
    main()
