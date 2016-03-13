#!/usr/bin/env python3

import wiringpi2 as wp2
import time
import signal

wp2.wiringPiSetup()

roof_opened_sensor1 = 13
roof_closed_sensor1 = 12
roof_motor_start_relay1 = 0
roof_motor_direction_relay2 = 1
green_button = 18

received_signal = 0

#kill -SIGUSR1 13534
# https://docs.python.org/3/library/signal.html#signal.signal
def signal_handler(signum, stack_frame):
	global received_signal
	print("*** signal_handler received:", signum)
	received_signal = signum

print(time.strftime("%Y%m%d_%H%M%S"), "Set up signal_handler")
signal.signal(signal.SIGUSR1, signal_handler)
signal.signal(signal.SIGUSR2, signal_handler)

print(time.strftime("%Y%m%d_%H%M%S"), "Set up green_button as input")
wp2.pinMode(green_button, wp2.GPIO.INPUT)
wp2.pullUpDnControl(green_button, wp2.GPIO.PUD_UP)

print(time.strftime("%Y%m%d_%H%M%S"), "Set up roof closed and opened sensors as input")
wp2.pinMode(roof_closed_sensor1, wp2.GPIO.INPUT)
wp2.pinMode(roof_opened_sensor1, wp2.GPIO.INPUT)

print(time.strftime("%Y%m%d_%H%M%S"), "Set up left and right relay as output")
wp2.pinMode(roof_motor_start_relay1,	 wp2.GPIO.OUTPUT)
wp2.pinMode(roof_motor_direction_relay2, wp2.GPIO.OUTPUT)

def waitForButton(pin):
		global received_signal
		while True:
				while wp2.digitalRead(pin) == True and received_signal == 0:
						time.sleep(0.01)
				# signal ?
				if received_signal != 0:
					print("Signal ", received_signal)
					received_signal = 0
					return True
				# possible button press start
				pressed_time = 0
				while wp2.digitalRead(pin) == False:
						time.sleep(0.01)
						pressed_time += 10
				if pressed_time >= 100:
						print("Pressed for", pressed_time, "ms")
						return True
				else:
						print("Too brief press:", pressed_time, "ms")

try:
	print("\n",time.strftime("%Y%m%d_%H%M%S"), "Wait for green button to start and make sure the roof is closed")
	waitForButton(green_button)
	print(time.strftime("%Y%m%d_%H%M%S"), "Green button pressed or signal received")
	time.sleep(1)

	if not wp2.digitalRead(roof_closed_sensor1) :
		print(time.strftime("%Y%m%d_%H%M%S"), "Roof not yet closed -> close")
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.HIGH)  # roof close direction
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.HIGH)   # start motor
		print("\n",time.strftime("%Y%m%d_%H%M%S"), "Wait for right / roof-closed sensor")

	while not wp2.digitalRead(roof_closed_sensor1) and wp2.digitalRead(green_button) and received_signal == 0:
		pass
	received_signal = 0
	wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
	wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction

	print(time.strftime("%Y%m%d_%H%M%S"), "Roof is closed, starting main loop")
	time.sleep(1)

	while True:
		print("\n",time.strftime("%Y%m%d_%H%M%S"), "Wait for green button to open roof")
		waitForButton(green_button)
		print(time.strftime("%Y%m%d_%H%M%S"), "Green button pressed or signal received")
		time.sleep(1)

		print(time.strftime("%Y%m%d_%H%M%S"), "Opening roof")

		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.HIGH)   # start motor

		print("\n",time.strftime("%Y%m%d_%H%M%S"), "Wait for left / roof-open sensor")
		while not wp2.digitalRead(roof_opened_sensor1) and wp2.digitalRead(green_button) and received_signal == 0:
			pass
		received_signal = 0
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.HIGH)  # roof close direction

		print(time.strftime("%Y%m%d_%H%M%S"), "Roof is open")
		time.sleep(1)

		print("\n",time.strftime("%Y%m%d_%H%M%S"), "Wait for control switch to close roof")
		waitForButton(green_button)
		print(time.strftime("%Y%m%d_%H%M%S"), "Green button pressed or signal received")
		time.sleep(1)
	
		print(time.strftime("%Y%m%d_%H%M%S"), "Closing roof")
	
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.HIGH)  # roof close direction
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.HIGH)   # start motor
	
		print("\n",time.strftime("%Y%m%d_%H%M%S"), "Wait for right / roof-closed sensor")
		while not wp2.digitalRead(roof_closed_sensor1) and wp2.digitalRead(green_button) and received_signal == 0:
			pass
		received_signal = 0
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction
	
		print(time.strftime("%Y%m%d_%H%M%S"), "Roof is closed")
		time.sleep(1)

except KeyboardInterrupt:
	print(time.strftime("%Y%m%d_%H%M%S"), "KeyboardInterrupt caught. Stop any running motor")
	wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
	wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction

print(time.strftime("%Y%m%d_%H%M%S"), "Clean stop")
quit()

