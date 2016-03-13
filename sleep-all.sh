#!/bin/bash
set -x
set -e

# 3
# 20160220 lap moved from 5 to 3
#./wake-lap2.sh
ssh lap2 poweroff ||:
sleep 60
./relay_0-7_low-high.py 3 low

# 4
#./wake-other-imaging-equpiment.sh
./relay_0-7_low-high.py 4 low

# 6
#./wake-mount.sh
./relay_0-7_low-high.py 6 low

# 7
#./wake-roof-motor-controller.sh
./relay_0-7_low-high.py 7 low


