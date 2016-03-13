// gcc readAllMyI2cDevices.c -o readAllMyI2cDevices -l bcm2835 -lrt
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

#define AVG 1   //averaging samples

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

int readMLX(int address, char *sensor) {
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
    bcm2835_init();
    bcm2835_i2c_begin();
    bcm2835_i2c_set_baudrate(25000);

//	while (1) {
		readBH1750(0x23);
		readMLX(0x5a, "BAA");
		readMLX(0x5b, "BCC");
//        sleep());
//	}
}

