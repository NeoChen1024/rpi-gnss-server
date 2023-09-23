/* ===================================== *
 * Rawlogger.cpp - UBX protocol logger	 *
 * Written by:  Neo_Chen (2023)		 *
 * ===================================== */

#include "ubx.hpp"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdint.h>
#include <endian.h>
#include <sys/stat.h>
#include <assert.h>
#include <errno.h>
#include <getopt.h>

#define RETURN_ERR \
	return 1

using namespace UBX;

#define CHAR_CHECK(wasted)				\
	if(c == EOF)					\
	{						\
		return c;				\
	}						\
	if(c == UBX_SYNC1)				\
	{						\
		if(fgetc(fp) == UBX_SYNC2)		\
		{					\
			ungetc(UBX_SYNC2, fp);		\
			wasted_bytes += (wasted);	\
			goto resync_sync2;		\
		}					\
	}						\


int ubx_read_frame(FILE *fp, ubx_buf_t &buf)
{
	int c = 0;
	size_t length = 0;
	size_t wasted_bytes = 0;
	// Read until we get a sync char
resync:
	while (1)
	{
		c = fgetc(fp);
		if (c == EOF)
		{
			return c;
		}
		if (c == 0xb5)
		{
			break;
		}
		wasted_bytes++;
	}
	// Get SYNC2
resync_sync2:
	if(fgetc(fp) != 0x62)
	{
		goto resync;
	}
	buf.clear();
	if(wasted_bytes > 0)
	{
		fprintf(stderr, "ubx_read_frame(): WASTED %zd Bytes\n", wasted_bytes);
	}
	// Get class_id & msg_id
	buf.push_back(c = fgetc(fp));
	CHAR_CHECK(1);
	buf.push_back(c = fgetc(fp));
	CHAR_CHECK(2);
	// Get length
	buf.push_back(c = fgetc(fp));
	CHAR_CHECK(3);
	length = c & 0xff; // LSB
	buf.push_back(c = fgetc(fp));
	CHAR_CHECK(4);
	length |= (c << 8) & 0xff00; // MSB

	// Now we know the length, read the payload & checksum
	for(size_t i = 0; i < length + 2; i++)
	{
		buf.push_back(c = fgetc(fp));
		if(c == EOF)
		{
			return c;
		}
	}
	return c;
}

void print_status_line(ubx_nav_pvt &pvt)
{
	fprintf(stderr, "iTOW=%07u %04u/%02hhu/%02hhu %02hhu:%02hhu:%02hhu, Sats: %02hhu\r",
		pvt.data.iTOW,
		pvt.data.year, pvt.data.month, pvt.data.day, pvt.data.hour, pvt.data.min, pvt.data.sec,
		pvt.data.numSV);
}

int main(int argc, char *argv[])
{
	bool debug = false;
	FILE *readin = stdin;
	FILE *writeout = NULL;

	int opt;

	while((opt = getopt(argc, argv, "f:d")) != -1)
	{
		switch(opt)
		{
		case 'f':
			readin = fopen(optarg, "rb");
			if(readin == NULL)
			{
				perror(optarg);
				RETURN_ERR;
			}
			break;
		case 'd':
			debug = true;
			break;
		default:
			fprintf(stderr, "Usage: %s [-f input_file] [-d]\n", argv[0]);
			RETURN_ERR;
		}
	}

	ubx_nav_pvt last_pvt;

	while(1)
	{
		ubx_buf_t buf;
		int ret = ubx_read_frame(readin, buf);
		if(ret == EOF)
		{
			break;
		}
		ubx_frame frame(buf);
		if(!frame.valid)
		{
			fprintf(stderr, "Invalid frame!\n");
			frame.dump(stderr);
			continue;
		}
		if(debug)
		{
			ubx_any_msg msg(frame);
			msg.dump(stderr);
		}
		ubx_nav_pvt pvt(frame);
		if(pvt.valid)
		{
			//pvt.dump(stderr);
			
			/* Open new file if either no file is open, or the PVT day is changed */
			if(writeout == NULL || pvt.data.day != last_pvt.data.day)
			{
				if(writeout != NULL)
					fclose(writeout);
				/* if month changed, make new directory */
				char dirname[64];
				if(pvt.data.month != last_pvt.data.month)
				{
					snprintf(dirname, 64, "%04u-%02hhu", pvt.data.year, pvt.data.month);
					if(mkdir(dirname, 0755) != 0)
					{
						if(errno != EEXIST)
						{
							perror(dirname);
							RETURN_ERR;
						}
					}
					fprintf(stderr, "\nCreated directory %s\n", dirname);
				}
				char filename[128];
				snprintf(filename, 128, "%s/%04u%02hhu%02hhuT%02hhu%02hhu%02hhu.ubx",
					dirname,
					pvt.data.year, pvt.data.month, pvt.data.day, pvt.data.hour, pvt.data.min, pvt.data.sec);
				writeout = fopen(filename, "wb");
				if(writeout == NULL)
				{
					fprintf(stderr, "Unable to open file %s!\n", filename);
					RETURN_ERR;
				}
				fprintf(stderr, "\nOpened file %s\n", filename);
			}

			last_pvt = pvt;

			/* Print current status */
			print_status_line(pvt);
		}

		/* Passthrough */
		if(writeout != NULL)
			frame.write(writeout);
	}
	fputs("\nEOF!?\n", stderr);
	return 0;
}