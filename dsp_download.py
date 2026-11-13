#!/usr/bin/env python3
"""
dsp_download.py — DSP release 镜像下载工具

数据源: http://172.16.45.24/dsp_release/
  ├── <project>/            (项目, 如 opt-opt_tl3588)
  │    ├── <version>/       (时间版本, 如 20260728181038, 默认取最新)
  │    │    └── <image>     (镜像文件)

镜像名忽略时间: 匹配时会自动剥离文件名中的 14 位时间戳(如 20260728181038),
因此一个镜像名可在任意时间版本上通配匹配。支持 '*' 通配符。
依赖: requests (如未安装: pip install requests)
"""

import argparse
import os
import re
import sys

import requests

BASE_URL = "http://172.16.45.24/dsp_release"
TIME_RE = re.compile(r"\d{14}")  # 时间版本戳, 如 20260728181038

UA = {"User-Agent": "dsp_download/1.0"}


# ---------- 基础 HTTP ----------
def get_dir(url):
    """抓取 apache 目录列表, 返回 {名称: 完整URL}. 目录项带结尾'/', 文件不带."""
    r = requests.get(url, headers=UA, timeout=30)
    if r.status_code == 404:
        sys.exit(f"404: 路径不存在 -> {url}")
    r.raise_for_status()
    html = r.text
    return {
        m.group(1): url.rstrip("/") + "/" + m.group(1)
        for m in re.finditer(r'<a href="([^"]+)"', html)
        if not m.group(1).startswith(("../", "/")) and m.group(1) != ""
    }


def list_projects():
    return sorted(n.rstrip("/") for n in get_dir(BASE_URL).keys())


def list_versions(project):
    entries = get_dir(f"{BASE_URL}/{project}")
    return {n.rstrip("/"): u for n, u in entries.items() if n.endswith("/")}


def list_images(project, version):
    entries = get_dir(f"{BASE_URL}/{project}/{version}")
    return {n: u for n, u in entries.items() if not n.endswith("/")}


# ---------- 时间无关镜像名匹配 ----------
def strip_time(name):
    """去掉文件名中的时间版本戳(14位数字), 实现跨版本通配."""
    return TIME_RE.sub("*", name)


def match_images(images, pattern):
    """pattern 可含'*', 忽略时间戳后模糊匹配文件名. 返回匹配到的文件名列表."""
    pat = strip_time(pattern).lower()
    pat_re = re.compile(re.escape(pat).replace(r"\*", ".*"))
    return sorted(n for n in images if pat_re.fullmatch(strip_time(n).lower()))


def pick_latest(versions):
    """选时间版本戳数字最大的作为最新版本."""
    ts = [v for v in versions if v.isdigit()]
    ts.sort()
    return ts[-1] if ts else (sorted(versions)[-1] if versions else None)


# ---------- 主要逻辑 ----------
def cmd_projects(args):
    for p in list_projects():
        print(p)


def cmd_versions(args):
    versions = list_versions(args.project)
    if not versions:
        sys.exit(f"项目 '{args.project}' 不存在或无版本目录")
    latest = pick_latest(versions)
    for v in sorted(versions):
        mark = "  <-- 最新" if v == latest else ""
        print(f"{v}{mark}")


def _print_images(project, version, image_filter=None):
    """列出某版本的镜像, 若给 image_filter 则只列匹配项."""
    images = list_images(project, version)
    if image_filter:
        m = match_images(list(images), image_filter)
        images = {n: images[n] for n in m}
        if not images:
            sys.exit(
                f"在 {project}/{version} 中未找到匹配 '{image_filter}' 的镜像.\n"
                f"全部镜像:\n  " + "\n  ".join(sorted(list_images(project, version))))
    print(f"\n# {project}/{version}  (共 {len(images)} 个镜像)")
    for n in sorted(images):
        print(n)


def cmd_download(args):
    versions = list_versions(args.project)
    if not versions:
        sys.exit(f"项目 '{args.project}' 不存在或无版本目录")
    version = args.version or pick_latest(versions)
    images = list_images(args.project, version)
    matches = match_images(images, args.image)
    if not matches:
        sys.exit(
            f"在 {args.project}/{version} 中未找到匹配 '{args.image}' 的镜像.\n"
            f"可用镜像:\n  " + "\n  ".join(sorted(images))
        )
    if len(matches) > 1:
        sys.exit(
            f"镜像名 '{args.image}' 匹配到多个文件, 请进一步指定:\n  "
            + "\n  ".join(matches)
        )
    name = matches[0]
    url = f"{BASE_URL}/{args.project}/{version}/{name}"
    out_dir = args.out or "."
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, name)
    print(f"下载 {url}\n  -> {dest}")

    with requests.get(url, headers=UA, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    _progress(done, total)
    print(f"\n完成: {dest}  ({done/1e6:.1f} MB)")


def _progress(done, total):
    if total:
        pct = done * 100 // total
        sys.stderr.write(f"\r  {pct:3d}%  {done/1e6:.0f}/{total/1e6:.0f} MB")
        sys.stderr.flush()


def main():
    ap = argparse.ArgumentParser(
        prog="dsp_download.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "DSP release 镜像下载工具.\n"
            "数据源: http://172.16.45.24/dsp_release/  (目录: <project>/<time-version>/<image>)\n"
            "镜像名忽略时间戳(14 位时间戳自动剥离), 同一名字可跨版本通配匹配, 支持 '*' 通配符."
        ),
        epilog=EXAMPLE_TEXT,
    )

    # 动作(互斥, 必选)
    act = ap.add_mutually_exclusive_group(required=True)
    act.add_argument("-l", "--list", action="store_true",
                     help="列出内容, 依参数决定: 项目 / 版本 / 镜像(见下)")
    act.add_argument("-d", "--download", action="store_true",
                     help="下载指定项目的镜像")

    # 参数(命名选项, 顺序可任意调换)
    ap.add_argument("-p", "--project", metavar="NAME",
                    help="项目名, 如 opt-opt_tl3588")
    ap.add_argument("-I", "--image", metavar="NAME",
                    help="镜像名(忽略时间戳, 支持 * 通配), 如 update.img")
    ap.add_argument("-v", "--version", metavar="TIME",
                    help="时间版本(如 20260721161556), 默认取最新")
    ap.add_argument("-o", "--out", metavar="DIR", default=".",
                    help="保存目录, 默认当前目录 (.)")

    args = ap.parse_args()

    if args.list:
        cmd_list(args)
    elif args.download:
        _require(args, "project", "download")
        _require(args, "image", "download")
        cmd_download(args)


def cmd_list(args):
    """list 上下文相关:
    无项目 -> 项目; 有项目无版本 -> 版本 + 最新版本的镜像; 有项目+版本 -> 该版本镜像."""
    if not args.project:
        cmd_projects(args)
    elif args.version:
        _print_images(args.project, args.version, args.image)
    else:
        versions = list_versions(args.project)
        if not versions:
            sys.exit(f"项目 '{args.project}' 不存在或无版本目录")
        latest = pick_latest(versions)
        print("== 版本 ==")
        for v in sorted(versions):
            print(f"{v}{'  <-- 最新' if v == latest else ''}")
        _print_images(args.project, latest, args.image)


def _require(args, name, action):
    if not getattr(args, name):
        ap_error(f"'{action}' 需要参数 --{name}")
        sys.exit(2)


def ap_error(msg):
    print(f"dsp_download.py: error: {msg}", file=sys.stderr)


EXAMPLE_TEXT = """\
list 依参数决定列什么:
  -l                      列出所有项目
  -l -p <project>         列出所有版本 + 最新版本的镜像
  -l -p <project> -v <ver> 列出该版本下的所有镜像
  (-I <img> 可仅列匹配的镜像, 支持 * 通配)

示例:
  # 列出所有项目
  python3 dsp_download.py -l

  # 列出 opt-opt_tl3588 的所有版本 + 最新版本镜像
  python3 dsp_download.py -l -p opt-opt_tl3588

  # 列出指定版本下的所有镜像
  python3 dsp_download.py -l -p opt-opt_tl3588 -v 20260721161556

  # 列出某版本下匹配的镜像
  python3 dsp_download.py -l -p opt-opt_tl3588 -I '*.img'

  # 下载最新版本的 update.img (版本默认取最新)
  python3 dsp_download.py -d -p opt-opt_tl3588 -I update.img

  # 下载指定版本并保存到目录 (参数顺序任意)
  python3 dsp_download.py -d -I boot.img -v 20260721161556 -p opt-opt_tl3588 -o /data

  # 下载带时间戳命名的 rootfs, 用 '*' 通配时间戳, 可跨版本匹配
  python3 dsp_download.py -d -p opt-opt_tl3588 -I 'qsemos-image-*.rootfs.cpio.gz'

常用简称:
  -l --list         -d --download
  -p --project      -I --image      -v --version   -o --out
"""


if __name__ == "__main__":
    main()
