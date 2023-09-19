/* ===================================== *
 * Rawlogger.cpp - UBX protocol logger	 *
 * Written by:  Neo_Chen (2023)		 *
 * ===================================== */


#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdint.h>
#include <endian.h>
#include <sys/stat.h>
#include <assert.h>
#include <errno.h>

#define UBX_SYNC1	0xB5
#define UBX_SYNC2	0x62
#define UBX_CLASS_NAV	0x01
#define UBX_ID_PVT	0x07
#define UBX_HEADER_SIZE	6
#define PVT_SIZE	92

const uint8_t ubx_nav_pvt[UBX_HEADER_SIZE] =
{
	UBX_SYNC1, UBX_SYNC2, UBX_CLASS_NAV, UBX_ID_PVT, 0x5C, 0x00
};

struct ubx_nav_pvt
{
	uint32_t iTOW;
	uint16_t year;
	uint8_t month;
	uint8_t day;
	uint8_t hour;
	uint8_t min;
	uint8_t sec;
	uint8_t valid;
	uint32_t tAcc;
	int32_t nano;
	uint8_t fixType;
	uint8_t flags;
	uint8_t flags2;
	uint8_t numSV;
	int32_t lon;
	int32_t lat;
	int32_t height;
	int32_t hMSL;
	uint32_t hAcc;
	uint32_t vAcc;
	int32_t velN;
	int32_t velE;
	int32_t velD;
	int32_t gSpeed;
	int32_t headMot;
	uint32_t sAcc;
	uint32_t headAcc;
	uint16_t pDOP;
	uint8_t reserved1[6];
	int32_t headVeh;
	uint8_t reserved2[4];
} __attribute((packed));

struct ubx_nav_pvt pvt, last_pvt;

void print_pvt(struct ubx_nav_pvt pvt)
{
		fputs("=====================\n", stderr);
		fprintf(stderr, "iTOW: %u\n", pvt.iTOW);
		fprintf(stderr, "Date: %04u/%02hhu/%02hhu %02hhu:%02hhu:%02hhu\n",
			pvt.year, pvt.month, pvt.day, pvt.hour, pvt.min, pvt.sec);
		fprintf(stderr, "valid: %u\n", pvt.valid);
		fprintf(stderr, "tAcc: %u\n", pvt.tAcc);
		fprintf(stderr, "nano: %d\n", pvt.nano);
		fprintf(stderr, "fixType: %u\n", pvt.fixType);
		fprintf(stderr, "flags: %u\n", pvt.flags);
		fprintf(stderr, "flags2: %u\n", pvt.flags2);
		fprintf(stderr, "numSV: %u\n", pvt.numSV);
		fprintf(stderr, "lon: %d, lat: %d\n", pvt.lon, pvt.lat);
		fprintf(stderr, "height: %d, hMSL: %d\n", pvt.height, pvt.hMSL);
		fprintf(stderr, "hAcc: %u, vAcc: %u\n", pvt.hAcc, pvt.vAcc);
		fprintf(stderr, "velN/E/D: %d/%d/%d\n", pvt.velN, pvt.velE, pvt.velD);
		fprintf(stderr, "gSpeed: %d\n", pvt.gSpeed);
		fprintf(stderr, "headMot: %d\n", pvt.headMot);
		fprintf(stderr, "sAcc: %u\n", pvt.sAcc);
		fprintf(stderr, "headAcc: %u\n", pvt.headAcc);
		fprintf(stderr, "pDOP: %u\n", pvt.pDOP);
		fprintf(stderr, "headVeh: %d\n", pvt.headVeh);
}

int main(int argc, char *argv[])
{
	FILE *fp = NULL;
	int c = 0;
	int match_cnt = 0;
	uint8_t pvt_buf[PVT_SIZE];
	uint8_t pvt_cksum[2]; /* UBX Checksum */
	uint8_t cksum[2]; /* cksum[0] is CK_A, cksum[1] is CK_B */

	/* zero last_pvt */
	memset(&last_pvt, 0, sizeof(last_pvt));

	while(1)
	{
		c = getc(stdin);

		if(c == EOF)
			break;
		if(c == ubx_nav_pvt[match_cnt])
			match_cnt++;
		else
			match_cnt = 0;
		
		if(match_cnt != UBX_HEADER_SIZE)
			goto nextchar;

		match_cnt = 0; // reset match counter

		/* Message type matched, try parsing it */
		size_t bcnt;
		if((bcnt = fread(pvt_buf, 1, PVT_SIZE, stdin)) != PVT_SIZE)
		{
			/* If unable to read in, bailout */
			fprintf(stderr, "Unable to read PVT message!\n");
			continue; // go back to read the next char
		}
		/* Read checksum */
		if((bcnt = fread(pvt_cksum, 1, 2, stdin)) != 2)
		{
			/* If unable to read in, bailout */
			fprintf(stderr, "Unable to read checksum!\n");
			continue; // go back to read the next char
		}
		/* Verify checksum */
		cksum[0] = 0;
		cksum[1] = 0;
		for(int i = 2; i < UBX_HEADER_SIZE; i++)
		{
			cksum[0] += ubx_nav_pvt[i];
			cksum[1] += cksum[0];
		}
		for(int i = 0; i < PVT_SIZE; i++)
		{
			cksum[0] += pvt_buf[i];
			cksum[1] += cksum[0];
		}

		if(cksum[0] != pvt_cksum[0] || cksum[1] != pvt_cksum[1])
		{
			/* Checksum mismatch, bailout */
			fprintf(stderr, "Checksum mismatch!\t");
			fprintf(stderr, "Expected: %02X %02X\t", cksum[0], cksum[1]);
			fprintf(stderr, "Received: %02X %02X\n", pvt_cksum[0], pvt_cksum[1]);
			continue; // go back to read the next char
		}

		/* Checksum matched, parse PVT by copying
		 * TODO: make it more portable
		 */
		memcpy(&pvt, pvt_buf, PVT_SIZE);
		// Endianness conversion
		pvt.iTOW = le32toh(pvt.iTOW);
		pvt.year = le16toh(pvt.year);
		pvt.tAcc = le32toh(pvt.tAcc);
		pvt.nano = le32toh(pvt.nano);
		pvt.lon = le32toh(pvt.lon);
		pvt.lat = le32toh(pvt.lat);
		pvt.height = le32toh(pvt.height);
		pvt.hMSL = le32toh(pvt.hMSL);
		pvt.hAcc = le32toh(pvt.hAcc);
		pvt.vAcc = le32toh(pvt.vAcc);
		pvt.velN = le32toh(pvt.velN);
		pvt.velE = le32toh(pvt.velE);
		pvt.velD = le32toh(pvt.velD);
		pvt.gSpeed = le32toh(pvt.gSpeed);
		pvt.headMot = le32toh(pvt.headMot);
		pvt.sAcc = le32toh(pvt.sAcc);
		pvt.headAcc = le32toh(pvt.headAcc);
		pvt.pDOP = le16toh(pvt.pDOP);
		pvt.headVeh = le32toh(pvt.headVeh);

		/* Print out parsed PVT */
		//print_pvt(pvt);

		/* Open new file if either no file is open, or the PVT day is changed */
		if(fp == NULL || pvt.day != last_pvt.day)
		{
			if(fp != NULL)
				fclose(fp);
			/* if month changed, make new directory */
			char dirname[64];
			if(pvt.month != last_pvt.month)
			{
				snprintf(dirname, 64, "%04u-%02hhu", pvt.year, pvt.month);
				if(mkdir(dirname, 0755) != 0)
				{
					if(errno != EEXIST)
					{
						perror(dirname);
						return 1;
					}
				}
				fprintf(stderr, "\nCreated directory %s\n", dirname);
			}
			char filename[128];
			snprintf(filename, 128, "%s/%04u%02hhu%02hhuT%02hhu%02hhu%02hhu.ubx",
				dirname,
				pvt.year, pvt.month, pvt.day, pvt.hour, pvt.min, pvt.sec);
			fp = fopen(filename, "wb");
			if(fp == NULL)
			{
				fprintf(stderr, "Unable to open file %s!\n", filename);
				return 1;
			}
			fprintf(stderr, "\nOpened file %s\n", filename);
		}

		/* Print current status */
		fprintf(stderr, "iTOW=%07u %04u/%02hhu/%02hhu %02hhu:%02hhu:%02hhu, Sats: %02hhu\r",
			pvt.iTOW,
			pvt.year, pvt.month, pvt.day, pvt.hour, pvt.min, pvt.sec,
			pvt.numSV);

		last_pvt = pvt;

		/* Write PVT to file */
		uint8_t writebuf[UBX_HEADER_SIZE + PVT_SIZE + 2];
		memcpy(writebuf, ubx_nav_pvt, UBX_HEADER_SIZE);
		memcpy(writebuf + UBX_HEADER_SIZE, pvt_buf, PVT_SIZE);
		memcpy(writebuf + UBX_HEADER_SIZE + PVT_SIZE, pvt_cksum, 2);

		if(fwrite(writebuf, 1, UBX_HEADER_SIZE + PVT_SIZE + 2, fp) != UBX_HEADER_SIZE + PVT_SIZE + 2)
		{
			fprintf(stderr, "Unable to write to file!\n");
			return 1;
		}
		continue; // go back to read the next char

		assert(0);	// should not reach here
	nextchar:
		if(fp != NULL)
			putc(c, fp);
		else
		{
			//putc(c, stdout);
		}
	}
	fputs("\nEOF!?\n", stderr);
	return 0;
}