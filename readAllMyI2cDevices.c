// gcc readAllMyI2cDevices.c -o readAllMyI2cDevices -l bcm2835 -lrt -lm
#include <stdio.h>
#include <bcm2835.h>
#include <stdlib.h>
#include <fcntl.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <time.h>
#include <sys/mman.h>
#include <errno.h>
#include <math.h>           // log() for dewpoint

#define AVG 1   //averaging samples

#define HEATER_PIN     RPI_V2_GPIO_P5_03   // GPIO28 / P5-3 -> TIP120 base (cloud-sensor heater). NOT P5_04 — that is GPIO29 = wPi 18 = the green-button line read by controller.py (root cause of 2026-06-15 roof self-cycling incident).
#define HEATER_ON_K    5.0                  // turn ON  if cap_T - dewpoint <  this (dewpoint margin)
#define HEATER_OFF_K   7.0                  // turn OFF if cap_T - dewpoint >  this (hysteresis)
#define WET_ON_K       5.0                  // turn ON  if cap_T - sky_T  <  this (foil suspected obstructed by water/snow)
#define WET_OFF_K      8.0                  // safe to turn off only above this (3 K hysteresis on the wet trigger)
#define HEATER_SAFETY_MAX_C   55.0          // PVC cap Vicat ~60 °C — runaway-only check; passive solar can hit ~54 °C
#define HEATER_SAFETY_HYST_K   5.0          // re-arm safety latch below MAX - HYST (i.e. 50 °C)

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

int readMLX(int address, char *sensor,
            double *sensor_temp_out, double *sky_temp_out) {
    unsigned char buf[6];
    unsigned char i, reg;
    double temp=0, calc=0, object_temp, sensor_temp;
    time_t t = time(NULL);
    struct tm tm = *localtime(&t);
	char rrdupdate[99];
	char whichrrd[99];
	char T_str[9];

    bcm2835_i2c_setSlaveAddress(address);

    calc=0;
    reg=7;
    for(i=0; i<AVG; i++) {
        bcm2835_i2c_begin();
        bcm2835_i2c_write (&reg, 1);
        bcm2835_i2c_read_register_rs(&reg,&buf[0],3);
        temp = (double) (((buf[1]) << 8) + buf[0]);
        temp = (temp * 0.02) - 0.01;
        temp = temp - 273.15;
        calc+=temp;
//        sleep(1);
    }
    object_temp=calc/AVG;
    calc=0;
    reg=6;
    for(i=0;i<AVG;i++) {
        bcm2835_i2c_begin();
        bcm2835_i2c_write (&reg, 1);
        bcm2835_i2c_read_register_rs(&reg,&buf[0],3);
        temp = (double) (((buf[1]) << 8) + buf[0]);
        temp = (temp * 0.02) - 0.01;
        temp = temp - 273.15;
        calc+=temp;
//        sleep(1);
    }
    sensor_temp=calc/AVG;
    printf("%04d-%02d-%02d %02d:%02d:%02d MLX %x T_sensor=%04.2f C, T_object=%04.2f C\n",
		   tm.tm_year+1900,
		   tm.tm_mon +1,
		   tm.tm_mday,
		   tm.tm_hour,
		   tm.tm_min,
		   tm.tm_sec,
		   address,
		   sensor_temp,
		   object_temp);
	sprintf(rrdupdate, "update skytemperature-%s.rrd -t %s_sensor:%s_sky N:%.2f:%.2f\n",
			sensor,
			sensor,
			sensor,
			sensor_temp,
			object_temp);
	sprintf(whichrrd, "skytemperature-%s", sensor);
	rrdUpdateSomething(whichrrd, rrdupdate);

	sprintf(T_str, "%04.2f\n", sensor_temp);
	valueUpdate(whichrrd, "sensor", T_str);

	sprintf(T_str, "%04.2f\n", object_temp);
	valueUpdate(whichrrd, "object", T_str);

	if (sensor_temp_out) *sensor_temp_out = sensor_temp;
	if (sky_temp_out)    *sky_temp_out    = object_temp;
}

int readAHT21B(int address,
               double *T_out, double *RH_out, double *dewpoint_out) {
    unsigned char buf[8];
    time_t t_now = time(NULL);
    struct tm tm = *localtime(&t_now);

    bcm2835_i2c_setSlaveAddress(address);

    // Soft reset — clears any half-finished previous state
    buf[0] = 0xBA;
    bcm2835_i2c_begin();
    bcm2835_i2c_write((char *)buf, 1);
    bcm2835_delay(20);

    // Calibration / init
    buf[0] = 0xBE; buf[1] = 0x08; buf[2] = 0x00;
    bcm2835_i2c_begin();
    bcm2835_i2c_write((char *)buf, 3);
    bcm2835_delay(10);

    // Trigger measurement
    buf[0] = 0xAC; buf[1] = 0x33; buf[2] = 0x00;
    bcm2835_i2c_begin();
    bcm2835_i2c_write((char *)buf, 3);
    bcm2835_delay(90);   // datasheet: > 80 ms

    // Read 6 bytes: status + 20-bit RH + 20-bit T (CRC byte not used here)
    if (bcm2835_i2c_read((char *)buf, 6) != BCM2835_I2C_REASON_OK) {
        fprintf(stderr, "AHT21B 0x%x: i2c read failed\n", address);
        return 0;
    }
    if (buf[0] & 0x80) {   // busy bit set -> data not ready
        fprintf(stderr, "AHT21B 0x%x: still busy\n", address);
        return 0;
    }

    unsigned int raw_RH = ((unsigned int)buf[1] << 12)
                        | ((unsigned int)buf[2] <<  4)
                        | (buf[3] >> 4);
    unsigned int raw_T  = ((unsigned int)(buf[3] & 0x0F) << 16)
                        | ((unsigned int)buf[4] <<  8)
                        | buf[5];

    double rh = (double)raw_RH * 100.0 / 1048576.0;
    double t  = (double)raw_T  * 200.0 / 1048576.0 - 50.0;

    // Magnus-Tetens (same constants as loops.pl for system-wide consistency)
    double gamma    = (17.27 * t) / (237.7 + t) + log((rh + 0.001) / 100.0);
    double dewpoint = (237.7 * gamma) / (17.27 - gamma);

    printf("%04d-%02d-%02d %02d:%02d:%02d AHT21B %x T=%.2f C RH=%.2f %% DP=%.2f C\n",
           tm.tm_year+1900, tm.tm_mon+1, tm.tm_mday,
           tm.tm_hour, tm.tm_min, tm.tm_sec,
           address, t, rh, dewpoint);

    char rrdupdate[160], v[16];
    sprintf(rrdupdate,
            "update tempandhum-outside.rrd -t temperature:humidity:dewpoint N:%.2f:%.2f:%.2f\n",
            t, rh, dewpoint);
    rrdUpdateSomething("tempandhum-outside", rrdupdate);

    sprintf(v, "%.2f\n", t);        valueUpdate("tempandhum-outside", "temperature", v);
    sprintf(v, "%.2f\n", rh);       valueUpdate("tempandhum-outside", "humidity",    v);
    sprintf(v, "%.2f\n", dewpoint); valueUpdate("tempandhum-outside", "dewpoint",    v);

    if (T_out)        *T_out        = t;
    if (RH_out)       *RH_out       = rh;
    if (dewpoint_out) *dewpoint_out = dewpoint;

    return 1;
}

int loadHeaterState(void) {
    int fd = shm_open("value_cloud-sensor-heater_state", O_RDONLY, 0666);
    if (fd < 0) return 0;
    char b[4] = {0};
    read(fd, b, 3);
    close(fd);
    return (b[0] == '1') ? 1 : 0;
}

int loadSafetyTripped(void) {
    int fd = shm_open("value_cloud-sensor-heater_safety_tripped", O_RDONLY, 0666);
    if (fd < 0) return 0;
    char b[4] = {0};
    read(fd, b, 3);
    close(fd);
    return (b[0] == '1') ? 1 : 0;
}

// Heater v2: dewpoint margin OR sky-delta low → ON. Both must be above their
// OFF thresholds to turn off. Safety: if cap_T exceeds HEATER_SAFETY_MAX_C
// the heater is force-latched OFF until cap_T drops HYST below MAX.
// All comparisons are signed — cap_T, dewpoint, and delta_t_max may all go
// negative in winter; abs() is intentionally NOT used (a busted-sensor
// delta_t of -5 K should stay -5 K and trip the wet-trigger, not be flipped
// to +5 K and look like a clear sky).
int decideHeater(double cap_T, double dewpoint, double delta_t_max,
                 int prev_state, int *safety_tripped) {
    // 1. SAFETY latch — only trip when the HEATER is responsible.
    // Passive solar load can push cap_T to ~54 °C on a sunny noon (observed
    // 2026-06-16 at 53.6 °C, heater off) without anything being wrong, so
    // the trip is gated on prev_state. Re-arm (clear) is unconditional —
    // once cap cools enough, the latch always releases.
    if (prev_state == 1 && cap_T > HEATER_SAFETY_MAX_C) {
        *safety_tripped = 1;
    } else if (cap_T < HEATER_SAFETY_MAX_C - HEATER_SAFETY_HYST_K) {
        *safety_tripped = 0;
    }
    if (*safety_tripped) return 0;

    double margin = cap_T - dewpoint;

    // 2. ON triggers (any)
    if (delta_t_max < WET_ON_K)   return 1;   // foil obstructed (wet / snow-covered)
    if (margin     < HEATER_ON_K) return 1;   // dewpoint margin too small
    // 3. OFF triggers (both required)
    if (delta_t_max > WET_OFF_K && margin > HEATER_OFF_K) return 0;
    // 4. else: hysteresis hold
    return prev_state;
}

void publishHeaterState(int state) {
    char rrdupdate[120], v[8];
    sprintf(rrdupdate, "update cloud-sensor-heater.rrd -t state N:%d\n", state);
    rrdUpdateSomething("cloud-sensor-heater", rrdupdate);
    sprintf(v, "%d\n", state);
    valueUpdate("cloud-sensor-heater", "state", v);
}

void publishSafetyTripped(int tripped) {
    char v[8];
    sprintf(v, "%d\n", tripped);
    valueUpdate("cloud-sensor-heater", "safety_tripped", v);
}

// Drop a one-shot flag at /dev/shm/cloud_sensor_safety_event whenever the
// safety latch transitions (0->1 trip, 1->0 recover). loops.pl picks the
// flag up on its next cycle, POSTs it to Mattermost (critical, @hans), and
// unlinks. So no spam: one message per actual transition.
void writeSafetyEvent(int now_tripped, double cap_T) {
    FILE *f = fopen("/dev/shm/cloud_sensor_safety_event", "w");
    if (!f) return;
    if (now_tripped) {
        fprintf(f, "TRIPPED cap_T=%.2fC (limit=%.1fC)", cap_T, (double)HEATER_SAFETY_MAX_C);
    } else {
        fprintf(f, "RECOVERED cap_T=%.2fC (re-arm below %.1fC)", cap_T, (double)HEATER_SAFETY_MAX_C - (double)HEATER_SAFETY_HYST_K);
    }
    fclose(f);
}

int readBH1750(int address) {
    time_t t = time(NULL);
    struct tm tm = *localtime(&t);
    char buf[3];
    unsigned char i, reg;
    double lux=0;
	char rrdupdate[99];
	char Lux_str[9];

    bcm2835_i2c_setSlaveAddress(address);

	buf[0] = 0x10;
	bcm2835_i2c_write(buf,1);
	sleep(1);
        for(i=0; i<AVG; i++) {
            bcm2835_i2c_read(buf, 2);
			lux = (buf[1] + (256 * buf[0])) / 1.2;
            sleep(1);
        }
        printf("%04d-%02d-%02d %02d:%02d:%02d BH1750 %x luminosity=%04.2f lx\n",
			   tm.tm_year+1900,
			   tm.tm_mon +1,
			   tm.tm_mday,
			   tm.tm_hour,
			   tm.tm_min,
			   tm.tm_sec,
			   address,
			   lux);
	sprintf(rrdupdate, "update luminosity.rrd -t luminosity N:%.2f\n",
			lux);
	rrdUpdateSomething("luminosity", rrdupdate);

	sprintf(Lux_str, "%04.2f\n", lux);
	valueUpdate("luminosity", "luminosity", Lux_str);
}

int main(int argc, char **argv)
{
    if (!bcm2835_init()) {
        fprintf(stderr, "bcm2835_init failed\n");
        return 1;
    }
    bcm2835_i2c_begin();
    bcm2835_i2c_set_baudrate(25000);

    // Heater GPIO: output, fail-safe LOW at start
    bcm2835_gpio_fsel(HEATER_PIN, BCM2835_GPIO_FSEL_OUTP);
    bcm2835_gpio_write(HEATER_PIN, LOW);

    double baa_T = 0, baa_sky = 0;
    double bcc_T = 0, bcc_sky = 0;
    double ext_T = 0, ext_RH = 0, ext_DP = 0;
    int aht_ok;

    readBH1750(0x23);
    readMLX  (0x5a, "BAA", &baa_T, &baa_sky);
    readMLX  (0x5b, "BCC", &bcc_T, &bcc_sky);
    aht_ok = readAHT21B(0x38, &ext_T, &ext_RH, &ext_DP);

    int prev_state          = loadHeaterState();
    int prev_safety_tripped = loadSafetyTripped();
    int safety_tripped      = prev_safety_tripped;
    double cap_T            = (baa_T + bcc_T) / 2.0;
    double delta_t_baa      = baa_T - baa_sky;
    double delta_t_bcc      = bcc_T - bcc_sky;
    double delta_t_max      = (delta_t_baa > delta_t_bcc) ? delta_t_baa : delta_t_bcc;
    int new_state;

    if (aht_ok) {
        new_state = decideHeater(cap_T, ext_DP, delta_t_max, prev_state, &safety_tripped);
    } else {
        // Fail-safe: humidity unknown → heater OFF. Still maintain the cap-T
        // safety latch — same heater-on-conditional trip + unconditional clear.
        if (prev_state == 1 && cap_T > HEATER_SAFETY_MAX_C) {
            safety_tripped = 1;
        } else if (cap_T < HEATER_SAFETY_MAX_C - HEATER_SAFETY_HYST_K) {
            safety_tripped = 0;
        }
        new_state = 0;
    }

    bcm2835_gpio_write(HEATER_PIN, new_state ? HIGH : LOW);
    publishHeaterState(new_state);
    publishSafetyTripped(safety_tripped);
    if (safety_tripped != prev_safety_tripped) {
        writeSafetyEvent(safety_tripped, cap_T);
    }

    bcm2835_i2c_end();
    bcm2835_close();
    return 0;
}

