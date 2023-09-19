Raspberry Pi GNSS NTP & RTK Server Project
==========================================
Main Target: Arch Linux ARM on Raspberry Pi 3B+ with minimal external hardwares  


### Containing files:
* config.txt
* cmdline.txt
* chronyd config excerpt
* rtkserv.sh: RTKLib str2str startup script
* daily-ubx.sh: Collect Raw UBX data (executed by cron)
* rawlogger: a new method of collecting raw UBX stream
