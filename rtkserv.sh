#!/bin/sh
exec str2str -a 'BeiTian BT-800' -i 'u-blox ZED-F9P' -opt -TADJ=1 \
	-px XX YY ZZ \
	-msg '1077,1087,1097,1107,1117,1127,1005,1004,1012,1007,1017,1019,1020,1033,1045' \
	-in 'serial://ttyAMA2:921600#ubx' \
	-out 'tcpsvr://:2001#rtcm3' \
	-out 'ntrips://:XXXXXXXXXXXXX@www.RTK2go.com:2101/XXXXXXX#rtcm3'
