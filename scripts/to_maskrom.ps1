curl.exe "http://localhost:18052/api/boards/tl3588/action?action=reset"
curl.exe -X POST -H "Content-Type: application/json" --data-binary "@$PSScriptRoot\to_maskrom_send_keys.json" http://172.16.33.54:18081/send_keys
Start-Sleep -Seconds 8
curl.exe -X POST -H "Content-Type: application/json" --data-binary "@$PSScriptRoot\to_maskrom_mmc.json" http://172.16.33.54:18081/command_block
Start-Sleep -Seconds 3
curl.exe "http://localhost:18052/api/boards/tl3588/action?action=reset"
