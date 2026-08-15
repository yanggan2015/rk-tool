# rk-tool

Windows 下用 **CLI** 烧写瑞芯微 `update.img`（不依赖 RKDevTool GUI）。

详见 **[说明书.md](说明书.md)**。

## 快速开始

1. 管理员运行 `tools\DriverAssistant\DriverInstall.exe` 安装驱动  
2. 将 `update.img` 放到 `firmware\`  
3. 设备进入 Loader / Maskrom 后执行：

```bat
scripts\flash-update.bat
```
