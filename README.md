# rk-tool

Windows 命令行烧写瑞芯微固件（`upgrade_tool`），不依赖 RKDevTool GUI。

入口：

- `flash.bat` → 调用 `rk.py`
- `rk.py`：烧写逻辑 + 按板型选 MiniLoader

## 用法

```bat
flash.bat boards
flash.bat ld
flash.bat db                 :: Maskrom 下按 PID 自动选 loader
flash.bat db -b ok3568
flash.bat ul -b ok3568
flash.bat uf update.img
flash.bat di boot boot.img -b ok3568
flash.bat rd
```

## Loader

`firmware/<板型>/MiniLoaderAll.bin`，来自 `forlinx-prebuild` 对应分支。

| 板型目录 | 芯片 | 默认 PID |
|---------|------|---------|
| ok3568 / rk3568 | RK3568 | 0x350a → ok3568 |
| ok3562 | RK3562 | 0x350d |
| tl3588 / ok3588 / opt3588 | RK3588 | 0x350b → tl3588 |

Maskrom 下单分区烧写会先 `DB` 对应 loader。
