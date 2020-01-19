#!/bin/bash

cd ~/rolloffroof/

while :; do
	T=$(date '+%Y%m%d_%H%M%S')
    echo "$T start loops.pl"
    rc=0; ./loops.pl || rc=$?

	T=$(date '+%Y%m%d_%H%M%S')
    echo "$T loops.pl exited with $rc"

    MOUNTED=0
    while [[ $MOUNTED -ne 1 ]]; do
	    T=$(date '+%Y%m%d_%H%M%S')
        echo "$T umount -afl -t nfs"
        umount -afl -t nfs

	    T=$(date '+%Y%m%d_%H%M%S')
        echo "$T sleep 60s"
        sleep 60

	    T=$(date '+%Y%m%d_%H%M%S')
        echo "$T mount -a -t nfs"
        mount -a -t nfs && MOUNTED=1
    done
done

