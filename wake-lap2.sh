#!/bin/bash

# 20160220 lap moved from 5 to 3
/root/relay_0-7_low-high.py 3 high

sleep 5

etherwake 00:1c:23:53:ca:cc

