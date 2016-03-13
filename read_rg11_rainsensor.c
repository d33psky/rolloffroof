#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <stdbool.h>
#include <sys/time.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <wiringPi.h>

//#define RG11_RELAY_PIN 29
#define RG11_RELAY_PIN 10
#define RELAY_PULSE_IN_MICROSECONDS 190000
#define RELAY_POLL_SLEEP_IN_MICROSECONDS 10000

#define MAX_DROPS_HISTORY 60

struct timeval pulse_edge_rising, pulse_edge_falling;
unsigned int pulses = 0;
unsigned int pulses_micro_seconds = 0;

void shmSetRaining(bool raining) {
	int shm_fd = -1;
	char *ptr = NULL;
	char s_raining[4] = "";

	strncpy(s_raining, (raining == true) ? "1\n" : "0\n", 3);
	//	shm_unlink("state_raining");

	piLock(1);
	shm_fd = shm_open("state_raining", O_CREAT | O_RDWR, 0666);
	if (-1 == shm_fd) {
		fprintf (stderr, "Unable to shm_open state_raining: %s\n", strerror (errno));
		exit(1);
	}
	if (-1 == ftruncate(shm_fd, 1+strlen(s_raining))) {
		fprintf (stderr, "Unable to ftruncate state_raining shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	ptr = mmap(NULL, 1+strlen(s_raining), PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
	if (MAP_FAILED == ptr) {
		fprintf (stderr, "Unable to mmap state_raining shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	if (-1 == close(shm_fd)) {
		fprintf (stderr, "Unable to close state_raining shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	strncpy(ptr, s_raining, 1+strlen(s_raining));
	if (-1 == munmap(ptr, 1+strlen(s_raining))) {
		fprintf (stderr, "Unable to munmap state_raining shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	piUnlock(1);
}

void valueUpdate(char *something, char *key, char *value) {
	int shm_fd;
	char *ptr;
	char valueFileName[99] = "value_";
	strcat(valueFileName, something);
	strcat(valueFileName, "_");
	strcat(valueFileName, key);
	shm_fd = shm_open(valueFileName, O_CREAT | O_RDWR, 0666);
	if (-1 == shm_fd) {
		fprintf (stderr, "Unable to shm_open %s: %s\n", valueFileName, strerror (errno));
		exit(1);
	}
	if (-1 == ftruncate(shm_fd, 1+strlen(value))) {
		fprintf (stderr, "Unable to ftruncate %s shm_fd: %s\n", valueFileName, strerror (errno));
		exit(1);
	}
	ptr = mmap (NULL, 1+strlen(value), PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
	if (MAP_FAILED == ptr) {
		fprintf (stderr, "Unable to mmap %s shm_fd: %s\n", valueFileName, strerror (errno));
		exit(1);
	}
	if (-1 == close(shm_fd)) {
		fprintf (stderr, "Unable to close %s shm_fd: %s\n", valueFileName, strerror (errno));
		exit(1);
	}
	strcpy(ptr, value);
	if (-1 == munmap(ptr, 1+strlen(value))) {
		fprintf (stderr, "Unable to munmap %s shm_fd: %s\n", valueFileName, strerror (errno));
		exit(1);
	}
}

PI_THREAD (registerRainDrops) {
	int drops = 0;
	unsigned int interval = 0;
	time_t t = time(NULL);
	struct tm tm = *localtime(&t);

	while (1) {
    	while (LOW == digitalRead(RG11_RELAY_PIN)) {
    		usleep(RELAY_POLL_SLEEP_IN_MICROSECONDS);
    	}
    	gettimeofday(&pulse_edge_rising, NULL);
		// printf("START tv_sec=%15u tv_usec=%15u\n", pulse_edge_rising.tv_sec, pulse_edge_rising.tv_usec);
    	while (HIGH == digitalRead(RG11_RELAY_PIN)) {
    		usleep(RELAY_POLL_SLEEP_IN_MICROSECONDS);
    	}
    	gettimeofday(&pulse_edge_falling, NULL);
		// printf("end   tv_sec=%15u tv_usec=%15u\n", pulse_edge_falling.tv_sec, pulse_edge_falling.tv_usec);
		interval = (1000000 * (pulse_edge_falling.tv_sec - pulse_edge_rising.tv_sec) + pulse_edge_falling.tv_usec) - pulse_edge_rising.tv_usec;
		drops = interval / RELAY_PULSE_IN_MICROSECONDS;
		t = time(NULL);
		tm = *localtime(&t);
		if (interval < RELAY_PULSE_IN_MICROSECONDS/2) {
			printf("%04d-%02d-%02d %02d:%02d:%02d SKIP too brief pulse of microseconds=%8u\n",
				   tm.tm_year+1900, tm.tm_mon +1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec,
				   interval);
		} else {
			printf("%04d-%02d-%02d %02d:%02d:%02d pulse microseconds=%8u -> drops=%3d\n",
				   tm.tm_year+1900, tm.tm_mon +1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec,
				   interval,
				   drops);

			shmSetRaining(true);

			piLock(0);
			pulses_micro_seconds += interval;
			pulses++;
			piUnlock(0);
		}

    	usleep(RELAY_POLL_SLEEP_IN_MICROSECONDS);
	}
}

void rrdUpdateRainSensor(char *rrdupdate) {
	int shm_fd;
	char *ptr;
	// shm_unlink("rrdupdate_rainsensor");
	shm_fd = shm_open("rrdupdate_rainsensor", O_CREAT | O_RDWR, 0666);
	if (-1 == shm_fd) {
		fprintf (stderr, "Unable to shm_open rrdupdate_rainsensor: %s\n", strerror (errno));
		exit(1);
	}
	if (-1 == ftruncate(shm_fd, 1+strlen(rrdupdate))) {
		fprintf (stderr, "Unable to ftruncate rrdupdate_rainsensor shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	ptr = mmap (NULL, 1+strlen(rrdupdate), PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
	if (MAP_FAILED == ptr) {
		fprintf (stderr, "Unable to mmap rrdupdate_rainsensor shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	if (-1 == close(shm_fd)) {
		fprintf (stderr, "Unable to close rrdupdate_rainsensor shm_fd: %s\n", strerror (errno));
		exit(1);
	}
	strcpy(ptr, rrdupdate);
	if (-1 == munmap(ptr, 1+strlen(rrdupdate))) {
		fprintf (stderr, "Unable to munmap rrdupdate_rainsensor shm_fd: %s\n", strerror (errno));
		exit(1);
	}
}

int main(void) {
	int drops;
	time_t t = time(NULL);
	struct tm tm = *localtime(&t);
	char output[99];
	char rrdupdate[99];
	int dropsHistory[MAX_DROPS_HISTORY];
	char dropsHistoryStr[MAX_DROPS_HISTORY * 5];
	int dropsPtr = 0;
	char dropStr[9];
	int totalHistoryDrops = 0;
	int i;

	for (i = 0; i < MAX_DROPS_HISTORY; i++) {
		dropsHistory[i] = 0;
	}
	dropsPtr = 0;

	if (wiringPiSetup() < 0) {
		fprintf (stderr, "Unable to setup wiringPi: %s\n", strerror (errno));
		return 1;
	}
	pinMode(RG11_RELAY_PIN, INPUT);
	pullUpDnControl(RG11_RELAY_PIN, PUD_DOWN);
	if (0 != piThreadCreate(registerRainDrops)) {
		fprintf (stderr, "Unable to create registerRainDrops thread: %s\n", strerror (errno));
		return 1;
	}

	while (1) {
		delay(60000);

		piLock(0);
		t = time(NULL);
		tm = *localtime(&t);
		drops = pulses_micro_seconds / RELAY_PULSE_IN_MICROSECONDS;
		sprintf(output, "%04d-%02d-%02d %02d:%02d:%02d pulses=%3u microseconds=%8u -> drops=%3d\n",
				tm.tm_year+1900, tm.tm_mon +1, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec,
				pulses,
				pulses_micro_seconds,
				drops);
		sprintf(rrdupdate, "update rainsensor.rrd -t pulses:drops N:%u:%u\n",
				pulses,
				drops);
		pulses = 0;
		pulses_micro_seconds = 0;
		piUnlock(0);

		printf(output);
		fflush(stdout);

		rrdUpdateRainSensor(rrdupdate);

		if (drops == 0) {
			shmSetRaining(false);
		}

		dropsHistory[dropsPtr] = drops;
		sprintf(dropsHistoryStr, "");
		for (i = dropsPtr; i >= 0; i--) {
			sprintf(dropStr, "%u ", dropsHistory[i]);
			strcat(dropsHistoryStr, dropStr);
		}
		for (i = MAX_DROPS_HISTORY - 1; i > dropsPtr; i--) {
			sprintf(dropStr, "%u ", dropsHistory[i]);
			strcat(dropsHistoryStr, dropStr);
		}

		dropsPtr++;
		if (dropsPtr >= MAX_DROPS_HISTORY) dropsPtr = 0;

		strcat(dropsHistoryStr, "\n");
		valueUpdate("raindrop", "history", dropsHistoryStr);

		totalHistoryDrops = 0;
		for (i = 0; i < MAX_DROPS_HISTORY; i++) {
			totalHistoryDrops += dropsHistory[i];
		}
		sprintf(dropStr, "%u\n", totalHistoryDrops);
		valueUpdate("raindrop", "sum", dropStr);
	}

	return 0;
}

