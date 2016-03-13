#!/usr/bin/env python3

import wiringpi2 as wp2
import time

wp2.wiringPiSetup()

roof_opened_sensor1 = 13
roof_closed_sensor1 = 12
roof_motor_start_relay1 = 0
roof_motor_direction_relay2 = 1
green_button = 18

print(time.strftime("%H%M%S"), "Set up green_button as input")
wp2.pinMode(green_button, wp2.GPIO.INPUT)
wp2.pullUpDnControl(green_button, wp2.GPIO.PUD_UP)

print(time.strftime("%H%M%S"), "Set up roof closed and opened sensors as input")
wp2.pinMode(roof_closed_sensor1, wp2.GPIO.INPUT)
wp2.pinMode(roof_opened_sensor1, wp2.GPIO.INPUT)

print(time.strftime("%H%M%S"), "Set up left and right relay as output")
wp2.pinMode(roof_motor_start_relay1,     wp2.GPIO.OUTPUT)
wp2.pinMode(roof_motor_direction_relay2, wp2.GPIO.OUTPUT)

try:
	print("\n",time.strftime("%H%M%S"), "Wait for green button down to start and make sure the roof is closed")
	while wp2.digitalRead(green_button) :
		pass
	print(time.strftime("%H%M%S"), "Green button pressed DOWN")
	time.sleep(0.1) # debounce
	print(time.strftime("%H%M%S"), "Wait for green button up")
	while not wp2.digitalRead(green_button) :
		pass
	print(time.strftime("%H%M%S"), "Green button pressed")
	time.sleep(1)
	
	if not wp2.digitalRead(roof_closed_sensor1) :
		print(time.strftime("%H%M%S"), "Roof not yet closed -> close")
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.HIGH)  # roof close direction
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.HIGH)   # start motor
		print("\n",time.strftime("%H%M%S"), "Wait for right / roof-closed sensor")
	
	while not wp2.digitalRead(roof_closed_sensor1) and wp2.digitalRead(green_button) :
		pass
	wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
	wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction
	
	print(time.strftime("%H%M%S"), "Roof is closed, starting main loop")
	time.sleep(1)
	
	while True:
		print("\n",time.strftime("%H%M%S"), "Wait for control switch to open roof")
		while wp2.digitalRead(green_button) :
			pass
		time.sleep(0.1) # debounce
		print(time.strftime("%H%M%S"), "Wait for control switch up")
		while not wp2.digitalRead(green_button) :
			pass
		print(time.strftime("%H%M%S"), "Control switch pressed")
		time.sleep(1)

		print(time.strftime("%H%M%S"), "Opening roof")

		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.HIGH)   # start motor

		print("\n",time.strftime("%H%M%S"), "Wait for left / roof-open sensor")
		while not wp2.digitalRead(roof_opened_sensor1) and wp2.digitalRead(green_button) :
			pass
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.HIGH)  # roof close direction

		print(time.strftime("%H%M%S"), "Roof is open")
		time.sleep(1)

		print("\n",time.strftime("%H%M%S"), "Wait for control switch to close roof")
		while wp2.digitalRead(green_button) :
			pass
		time.sleep(0.1) # debounce
		print(time.strftime("%H%M%S"), "Wait for control switch up")
		while not wp2.digitalRead(green_button) :
			pass
		print(time.strftime("%H%M%S"), "Control switch pressed")
		time.sleep(1)
	
		print(time.strftime("%H%M%S"), "Closing roof")
	
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.HIGH)  # roof close direction
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.HIGH)   # start motor
	
		print("\n",time.strftime("%H%M%S"), "Wait for right / roof-closed sensor")
		while not wp2.digitalRead(roof_closed_sensor1) and wp2.digitalRead(green_button) :
			pass
		wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
		wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction
	
		print(time.strftime("%H%M%S"), "Roof is closed")
		time.sleep(1)

except KeyboardInterrupt:
	print(time.strftime("%H%M%S"), "KeyboardInterrupt caught. Stop any running motor")
	wp2.digitalWrite(roof_motor_start_relay1, wp2.GPIO.LOW)  # stop motor
	wp2.digitalWrite(roof_motor_direction_relay2, wp2.GPIO.LOW) # roof open direction

print(time.strftime("%H%M%S"), "Clean stop")
quit()

