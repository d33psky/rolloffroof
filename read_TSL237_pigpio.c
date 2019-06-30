// gcc -o read_TSL237_pigpio read_TSL237_pigpio.c -lpigpio -lpthread -lrt -lm
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <unistd.h>
#include <math.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <string.h>

#include <pigpio.h>

#define MAX_GPIOS 32

#define OPT_P_MIN 1
#define OPT_P_MAX 1000
#define OPT_P_DEF 20

// -r 10
#define OPT_R_MIN 1
#define OPT_R_MAX 10
#define OPT_R_DEF 5

// -s 1
#define OPT_S_MIN 1
#define OPT_S_MAX 10
#define OPT_S_DEF 5

static volatile int g_pulse_count[MAX_GPIOS];
static volatile int g_reset_counts;
static uint32_t g_mask;

static int g_num_gpios;
static int g_gpio[MAX_GPIOS];

static int g_opt_p = OPT_P_DEF;
static int g_opt_r = OPT_R_DEF;
static int g_opt_s = OPT_S_DEF;
static int g_opt_t = 0;

void rrdUpdateSomething(char *something, char *rrdupdate) {
	int shm_fd;
	char *ptr;
	char rrd[99] = "rrdupdate_";
	strcat(rrd, something);
	shm_fd = shm_open(rrd, O_CREAT | O_RDWR, 0666);
	if (-1 == shm_fd) {
		fprintf (stderr, "Unable to shm_open %s: %s\n", rrd, strerror (errno));
		exit(1);
	}
	if (-1 == ftruncate(shm_fd, 1+strlen(rrdupdate))) {
		fprintf (stderr, "Unable to ftruncate %s shm_fd: %s\n", rrd, strerror (errno));
		exit(1);
	}
	ptr = mmap (NULL, 1+strlen(rrdupdate), PROT_READ | PROT_WRITE, MAP_SHARED, shm_fd, 0);
	if (MAP_FAILED == ptr) {
		fprintf (stderr, "Unable to mmap %s shm_fd: %s\n", rrd, strerror (errno));
		exit(1);
	}
	if (-1 == close(shm_fd)) {
		fprintf (stderr, "Unable to close %s shm_fd: %s\n", rrd, strerror (errno));
		exit(1);
	}
	strcpy(ptr, rrdupdate);
	if (-1 == munmap(ptr, 1+strlen(rrdupdate))) {
		fprintf (stderr, "Unable to munmap %s shm_fd: %s\n", rrd, strerror (errno));
		exit(1);
	}
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

void samples(const gpioSample_t *samples, int numSamples)
{
	static uint32_t state = 0;
	uint32_t high, level;
	int g, s;

	if (g_reset_counts) {
		g_reset_counts = 0;
		for (g=0; g<g_num_gpios; g++) g_pulse_count[g] = 0;
	}

	for (s=0; s<numSamples; s++) {
		level = samples[s].level;
		high = ((state ^ level) & g_mask) & level;
		state = level;
		/* only interested in low to high */
		if (high) {
			for (g=0; g<g_num_gpios; g++) {
				if (high & (1<<g_gpio[g])) g_pulse_count[g]++;
			}
		}
	}
}

int main(int argc, char *argv[])
{
	int i, g, wave_id, mode;
	gpioPulse_t pulse[2];
	double count[MAX_GPIOS];
	double factor = 5.0;
	char rrdupdate[99];
	double sqm = 0.0;
	double hz = 0;
	char SQM_str[9];

	/* get the gpios to monitor */
	g_num_gpios = 0;

	g = 7;

	g_gpio[g_num_gpios++] = g;
	g_mask |= (1<<g);

	g_opt_s = 1;
	g_opt_r = 10;

	printf("SQM on ");
	for (i=0; i<g_num_gpios; i++) printf("pin %d ", g_gpio[i]);
//	printf("Sample %d [us] Refresh %d [ds] ",
//		g_opt_s, g_opt_r); // sample and refresh rates in micro seconds, deci seconds

	gpioCfgClock(g_opt_s, 1, 1);

	if (gpioInitialise()<0) return 1;

	gpioWaveClear();

	pulse[0].gpioOn  = g_mask;
	pulse[0].gpioOff = 0;
	pulse[0].usDelay = g_opt_p;

	pulse[1].gpioOn  = 0;
	pulse[1].gpioOff = g_mask;
	pulse[1].usDelay = g_opt_p;

	gpioWaveAddGeneric(2, pulse);

	wave_id = gpioWaveCreate();

	/* monitor g_gpio level changes */

	gpioSetGetSamplesFunc(samples, g_mask);

	mode = PI_INPUT;

	if (g_opt_t) {
		gpioWaveTxSend(wave_id, PI_WAVE_MODE_REPEAT);
		mode = PI_OUTPUT;
	}

	for (i=0; i<g_num_gpios; i++) gpioSetMode(g_gpio[i], mode);

	g_reset_counts = 1;
//	while (1)
//	{
		gpioDelay(g_opt_r * factor * 100000);

		for (i=0; i<g_num_gpios; i++) count[i] = g_pulse_count[i] / factor;

		g_reset_counts = 1;

		hz = count[0];
		sqm = 22.0 - 2.5*log10(hz) - 0.95;
		printf("measured %.1f [Hz] -> %.2f [mag/arcsec^2] (= -0.95 calibration)\n",
			   hz,
			   sqm );
		sprintf(rrdupdate, "update sqm.rrd -t frequency:sqm N:%.1f:%.2f\n",
				hz,
				sqm);
		rrdUpdateSomething("sqm", rrdupdate);

		sprintf(SQM_str, "%04.2f\n", sqm);
		valueUpdate("sqm", "sqm", SQM_str);

//	}

	gpioTerminate();
	return (0);
}

