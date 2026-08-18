把要烧写的镜像放到本目录（推荐）。
脚本也会在工程根目录查找同名文件（例如根目录的 update.img）。

整包固件（推荐）：
  update.img

单分区镜像（按需放置，文件名需能识别分区）：
  boot.img
  uboot.img
  rootfs.img
  recovery.img
  misc.img
  oem.img
  userdata.img
  MiniLoaderAll.bin     Maskrom 下单分区烧写需要

用法：
  .\flash.bat                 烧写 firmware\update.img
  .\flash.bat boot            烧写 firmware\boot.img
  .\flash.bat rootfs          烧写 firmware\rootfs.img
  .\flash.bat uboot           烧写 firmware\uboot.img
  .\flash.bat help            查看全部用法
