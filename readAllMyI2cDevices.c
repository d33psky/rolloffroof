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
#define HEATER_ON_K    5.0                  // turn ON  if cap_T - dewpoint <  this
#define HEATER_OFF_K   7.0                  // turn OFF if cap_T - dewpoint >  this (hysteresis)

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

int decideHeater(double cap_T, double dewpoint, int prev_state) {
    double margin = cap_T - dewpoint;
    if (margin < HEATER_ON_K)  return 1;
    if (margin > HEATER_OFF_K) return 0;
    return prev_state;   // inside hysteresis band -> keep previous
}

void publishHeaterState(int state) {
    char rrdupdate[120], v[8];
    sprintf(rrdupdate, "update cloud-sensor-heater.rrd -t state N:%d\n", state);
    rrdUpdateSomething("cloud-sensor-heater", rrdupdate);
    sprintf(v, "%d\n", state);
    valueUpdate("cloud-sensor-heater", "state", v);
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

    int prev_state = loadHeaterState();
    int new_state;
    if (aht_ok) {
        double cap_T = (baa_T + bcc_T) / 2.0;
        new_state = decideHeater(cap_T, ext_DP, prev_state);
    } else {
        new_state = 0;                  // fail-safe: heater OFF when humidity unknown
    }
    bcm2835_gpio_write(HEATER_PIN, new_state ? HIGH : LOW);
    publishHeaterState(new_state);

    bcm2835_i2c_end();
    bcm2835_close();
    return 0;
}

