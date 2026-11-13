按板型存放 MiniLoaderAll.bin（Maskrom DB / UL 用）。

  firmware/ok3568/MiniLoaderAll.bin   RK3568 (PID 0x350a 默认)
  firmware/rk3568/MiniLoaderAll.bin
  firmware/ok3562/MiniLoaderAll.bin
  firmware/ok3588/MiniLoaderAll.bin
  firmware/tl3588/MiniLoaderAll.bin   RK3588 (PID 0x350b 默认)
  firmware/opt3588/MiniLoaderAll.bin

来源: forlinx-prebuild 对应分支 Image/MiniLoaderAll.bin 或 Image/loader.bin

用法:
  flash.bat boards
  flash.bat ld
  flash.bat db              自动按 PID 选板型
  flash.bat db -b ok3568
  flash.bat ul -b ok3568
  flash.bat uf update.img
  flash.bat di boot boot.img -b ok3568
