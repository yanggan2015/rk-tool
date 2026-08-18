# rk-tool

Windows 下用命令行烧写瑞芯微固件，不依赖 RKDevTool 图形界面。

支持：

- 整包烧写 `update.img`、单分区烧写
- 设备擦除、读芯片/存储/分区信息
- 多设备 `-s LocationID` 选择

完整说明见 [说明书.md](说明书.md)。

## 目录

```text
rk-tool/
├── flash.bat                 推荐入口
├── firmware/                 放置镜像（不入库）
├── scripts/                  烧写脚本
└── tools/                    官方 upgrade_tool 与 USB 驱动
```

## 快速开始

1. 管理员运行 `tools\DriverAssistant\DriverInstall.exe` 安装驱动
2. 将 `update.img`（以及可选的 `boot.img` / `uboot.img` / `rootfs.img`）放到 `firmware\`  
   根目录已有 `update.img` 时也可直接烧，不必先搬文件
3. 设备进入 **Loader** 或 **Maskrom** 后执行：

```bat
flash.bat
```

单分区：

```bat
flash.bat boot
flash.bat uboot
flash.bat rootfs
flash.bat boot uboot rootfs
```

查看设备 / 是否 Maskrom：

```bat
flash.bat status
flash.bat maskrom
flash.bat info
flash.bat erase
```

多设备时先 `flash.bat ld` 看 LocationID，再 `flash.bat -s 244 update`。

查看用法：`flash.bat help`
