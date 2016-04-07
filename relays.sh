#!/bin/bash

set -e			# be trigger-happy to be reliable
set -o pipefail # be trigger-happy to be reliable

#set -x

RELAYS="lap mount roof rest"
TASKLIST="wake sleep all $RELAYS"
declare -A TASKS
for task in $TASKLIST; do
	TASKS[$task]=0
done

for arg in $@; do
	for task in "${!TASKS[@]}"; do
		if [[ ${arg,,} == $task ]]; then
			TASKS[$task]=1
		fi
	done
done

readStates() {
	imaging_computer_power=$(cat /dev/shm/state_relay3)
	imaging_equipment_power=$(cat /dev/shm/state_relay4)
	mount_power=$(cat /dev/shm/state_relay6)
	roof_motor_power=$(cat /dev/shm/state_relay7)
	echo "$1 relay state: lap=$imaging_computer_power mount=$mount_power roof=$roof_motor_power rest=$imaging_equipment_power"
}

readStates Begin

if [[ ${TASKS['wake']} -eq 1 ]]; then
	ACTION_STR="Wake"
	ACTION_IF="low"
	ACTION_ALREADY="on"
	ACTION_RELAY="high"
elif [[ ${TASKS['sleep']} -eq 1 ]]; then
	ACTION_STR="Sleep"
	ACTION_IF="high"
	ACTION_ALREADY="off"
	ACTION_RELAY="low"
else
	echo "Usage: $0 Wake|Sleep [all] [lap] [mount] [roof] [rest]"
	exit 1
fi

if [[ ${TASKS['all']} -eq 1 ]]; then
	for task in $RELAYS; do
		TASKS[$task]=1
	done
fi

if [[ ${TASKS['lap']} -eq 1 ]]; then
	if [[ $imaging_computer_power == $ACTION_IF ]]; then
		echo "$ACTION_STR lap now:"
		if [[ ${TASKS['wake']} -eq 1 ]]; then
			/root/relay_0-7_low-high.py 3 $ACTION_RELAY
			echo "sleep 5"
			sleep 5
			echo "Send etherwake"
			etherwake 00:1c:23:53:ca:cc
		else
			echo "ssh lap2 poweroff"
			ssh lap2 poweroff ||:
			echo "sleep 60"
			sleep 60
			/root/relay_0-7_low-high.py 3 $ACTION_RELAY
		fi
	else
		echo "Skip $ACTION_STR lap, it's already $ACTION_ALREADY"
	fi
fi

if [[ ${TASKS['mount']} -eq 1 ]]; then
	if [[ $mount_power == $ACTION_IF ]]; then
		echo "$ACTION_STR mount now:"
		/root/relay_0-7_low-high.py 6 $ACTION_RELAY
	else
		echo "Skip $ACTION_STR mount, it's already $ACTION_ALREADY"
	fi
fi

if [[ ${TASKS['rest']} -eq 1 ]]; then
	if [[ $imaging_equipment_power == $ACTION_IF ]]; then
		echo "$ACTION_STR rest now:"
		/root/relay_0-7_low-high.py 4 $ACTION_RELAY
	else
		echo "Skip $ACTION_STR rest, it's already $ACTION_ALREADY"
	fi
fi

if [[ ${TASKS['roof']} -eq 1 ]]; then
	if [[ $roof_motor_power == $ACTION_IF ]]; then
		echo "$ACTION_STR roof motor now:"
		/root/relay_0-7_low-high.py 7 $ACTION_RELAY
	else
		echo "Skip $ACTION_STR roof motor, it's already $ACTION_ALREADY"
	fi
fi

readStates End

