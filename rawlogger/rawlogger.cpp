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

using namespace UBX;

int main(int argc, char *argv[])
{
	FILE *readin = NULL;
	FILE *writeout = NULL;

	// Get filename from command line
	if(argc > 1)
	{
		readin = fopen(argv[1], "rb");
		if(readin == NULL)
		{
			perror(argv[1]);
			return 1;
		}
	}
	else
	{
		readin = stdin;
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
							return 1;
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
					return 1;
				}
				fprintf(stderr, "\nOpened file %s\n", filename);
			}

			last_pvt = pvt;

			/* Print current status */
			fprintf(stderr, "iTOW=%07u %04u/%02hhu/%02hhu %02hhu:%02hhu:%02hhu, Sats: %02hhu\r",
				pvt.data.iTOW,
				pvt.data.year, pvt.data.month, pvt.data.day, pvt.data.hour, pvt.data.min, pvt.data.sec,
				pvt.data.numSV);
		}

		/* Passthrough */
		if(writeout != NULL)
			frame.write(writeout);
	}
	fputs("\nEOF!?\n", stderr);
	return 0;
}