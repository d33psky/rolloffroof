#!/bin/bash

while :; do
	T=$(date '+%Y%m%d_%H%M%S')

	if [[ -e "/dev/shm/state_relay1" ]]; then
		STATE=$(cat /dev/shm/state_relay1)
	else
		STATE="low"
	fi

	if [[ -e "/dev/shm/rrdupdate_tempandhum-picambucket" ]]; then
		TEMP_FLOAT=$(cat /dev/shm/rrdupdate_tempandhum-picambucket | cut -d : -f 4)
		TEMP=$(echo $TEMP_FLOAT|awk '{ printf "%.0f\n", $1 }')
	else
		TEMP="10"
	fi

	if [[ $TEMP -lt 10 ]]; then
		if [[ $STATE = "low" ]]; then
			echo "$T TEMP $TEMP < 10 and heater is OFF -> START heating"
			../relay_0-7_low-high.py 1 high
		else
			echo "$T TEMP $TEMP < 10 and heater is ON -> continue heating"
		fi
	else
		if [[ $STATE = "low" ]]; then
			echo "$T TEMP $TEMP >= 10 and heater is OFF -> stay idle"
		else
			echo "$T TEMP $TEMP >= 10 and heater is ON -> STOP heating"
			../relay_0-7_low-high.py 1 low
		fi
	fi

	sleep 60
done

