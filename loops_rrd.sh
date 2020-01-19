#!/bin/bash

LOOPWHAT=$1
PINGWHAT=$2

while :; do
	T=$(date '+%Y%m%d_%H%M%S')
    echo "$T start $LOOPWHAT"
    rc=0; $LOOPWHAT || rc=$?

	T=$(date '+%Y%m%d_%H%M%S')
    echo "$T $LOOPWHAT exited with $rc"

    PINGS=0
    while [[ $PINGS -ne 1 ]]; do
	    T=$(date '+%Y%m%d_%H%M%S')
        echo "$T sleep 60s"
        sleep 60

	    T=$(date '+%Y%m%d_%H%M%S')
        echo "$T ping -c3 $PINGWHAT"
        ping -c3 $PINGWHAT && PINGS=1
    done
done

