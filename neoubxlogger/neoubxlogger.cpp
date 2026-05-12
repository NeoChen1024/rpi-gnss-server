// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026, Kelei Chen

#include "ubx.hpp"
#include "ubx_nav.hpp"
#include "ubx_dump_gen.hpp"
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
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <ctime>

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
	char buf[128];
	fputc('\r', stderr);
	for(int i = 0; i < 80; i++)
		buf[i] = ' ';
	buf[80] = '\0';
	fputs(buf, stderr);
	fprintf(stderr, "\riTOW=%06u.%03u %10s %04u/%02hhu/%02hhu %02hhu:%02hhu:%02hhu, Sats: %02hhu",
		pvt.data.iTOW / 1000, pvt.data.iTOW % 1000,
		pvt.get_fix_type().c_str(),
		pvt.data.year, pvt.data.month, pvt.data.day, pvt.data.hour, pvt.data.min, pvt.data.sec,
		pvt.data.numSV);
}

static int tcp_connect(const char *host, int port)
{
	struct addrinfo hints, *res, *rp;
	char port_str[16];

	snprintf(port_str, sizeof(port_str), "%d", port);
	memset(&hints, 0, sizeof(hints));
	hints.ai_family = AF_UNSPEC;
	hints.ai_socktype = SOCK_STREAM;

	int err = getaddrinfo(host, port_str, &hints, &res);
	if(err != 0)
	{
		fprintf(stderr, "getaddrinfo: %s\n", gai_strerror(err));
		return -1;
	}

	int sockfd = -1;
	for(rp = res; rp != NULL; rp = rp->ai_next)
	{
		sockfd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
		if(sockfd < 0) continue;

		struct timeval tv = {5, 0};
		setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

		if(connect(sockfd, rp->ai_addr, rp->ai_addrlen) == 0)
			break;
		close(sockfd);
		sockfd = -1;
	}

	freeaddrinfo(res);
	return sockfd;
}

static int tcp_read_byte(int fd)
{
	unsigned char c;
	ssize_t n = read(fd, &c, 1);
	if(n == 1) return c;
	return EOF;
}

static int ubx_read_frame_tcp(int fd, ubx_buf_t &buf)
{
	int c;
	size_t length = 0;
	size_t wasted_bytes = 0;

resync:
	while((c = tcp_read_byte(fd)) != EOF)
	{
		if(c == UBX_SYNC1) break;
		wasted_bytes++;
	}
	if(c == EOF) return EOF;

	if(tcp_read_byte(fd) != UBX_SYNC2) goto resync;

	buf.clear();
	if(wasted_bytes > 0)
		fprintf(stderr, "ubx_read_frame(): WASTED %zd Bytes\n", wasted_bytes);

	for(int i = 0; i < 4; i++)
	{
		c = tcp_read_byte(fd);
		if(c == EOF) return EOF;
		buf.push_back(c);
	}

	length = (size_t)buf[2] | ((size_t)buf[3] << 8);

	for(size_t i = 0; i < length + 2; i++)
	{
		c = tcp_read_byte(fd);
		if(c == EOF) return EOF;
		buf.push_back(c);
	}

	return c;
}

struct Stats
{
	time_t last_print = 0;
	uint64_t period_bytes = 0;
	uint64_t period_frames = 0;
	uint64_t period_pvt = 0;
	uint64_t period_fix = 0;
};

static void print_stats(Stats &st, time_t now)
{
	double elapsed = difftime(now, st.last_print);
	if(elapsed < 1) return;
	double rate = st.period_bytes / elapsed / 1024.0;
	if(st.period_pvt > 0)
	{
		int pct = (int)(st.period_fix * 100 / st.period_pvt);
		fprintf(stderr, "\n[neoubxlogger stats] avg rate: %.1f KiB/s, frames: %lu, FIX %d%%\n",
			rate, (unsigned long)st.period_frames, pct);
	}
	else
	{
		fprintf(stderr, "\n[neoubxlogger stats] avg rate: %.1f KiB/s, frames: %lu, FIX ---%%\n",
			rate, (unsigned long)st.period_frames);
	}
	st.last_print = now;
	st.period_bytes = 0;
	st.period_frames = 0;
	st.period_pvt = 0;
	st.period_fix = 0;
}

int main(int argc, char *argv[])
{
	bool debug = false;
	bool no_write = false;
	bool quiet = false;
	FILE *readin = stdin;
	FILE *writeout = NULL;

	bool tcp_mode = false;
	std::string tcp_host;
	int tcp_port = 0;
	int sockfd = -1;

	Stats stats;

	setvbuf(stderr, NULL, _IONBF, 0);

	int opt;

	while((opt = getopt(argc, argv, "f:t:dnq")) != -1)
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
		case 't':
		{
			std::string spec(optarg);
			size_t colon = spec.rfind(':');
			if(colon == std::string::npos || colon == 0 || colon == spec.size() - 1)
			{
				fprintf(stderr, "Invalid TCP spec '%s'. Expected HOST:PORT\n", optarg);
				RETURN_ERR;
			}
			tcp_host = spec.substr(0, colon);
			tcp_port = std::stoi(spec.substr(colon + 1));
			tcp_mode = true;
			break;
		}
		case 'd':
			debug = true;
			break;
		case 'n':
			no_write = true;
			break;
		case 'q':
			quiet = true;
			break;
		default:
			fprintf(stderr, "Usage: %s [-f input_file] [-t HOST:PORT] [-n] [-d] [-q]\n", argv[0]);
			RETURN_ERR;
		}
	}

	if(tcp_mode && readin != stdin)
	{
		fprintf(stderr, "-f and -t are mutually exclusive\n");
		RETURN_ERR;
	}
	if(debug && quiet)
	{
		fprintf(stderr, "-d and -q are mutually exclusive\n");
		RETURN_ERR;
	}
	if(tcp_mode)
	{
		sockfd = tcp_connect(tcp_host.c_str(), tcp_port);
		if(sockfd < 0)
		{
			fprintf(stderr, "Failed to connect to %s:%d\n", tcp_host.c_str(), tcp_port);
			RETURN_ERR;
		}
		fprintf(stderr, "Connected to %s:%d\n", tcp_host.c_str(), tcp_port);
	}

	ubx_nav_pvt current_pvt, last_pvt;
	time_t stats_next = time(NULL) + 60;
	stats.last_print = time(NULL);

	while(1)
	{
		ubx_buf_t buf;

		if(tcp_mode)
		{
			int ret = ubx_read_frame_tcp(sockfd, buf);
			if(ret == EOF)
			{
				fprintf(stderr, "\nTCP %s:%d: connection lost, reconnecting in 2s...\n",
					tcp_host.c_str(), tcp_port);
				close(sockfd);
				sleep(2);
				sockfd = tcp_connect(tcp_host.c_str(), tcp_port);
				if(sockfd < 0)
				{
					fprintf(stderr, "Reconnect to %s:%d failed, retrying...\n",
						tcp_host.c_str(), tcp_port);
				}
				continue;
			}
		}
		else
		{
			if(ubx_read_frame(readin, buf) == EOF)
				break;
		}

		ubx_frame frame(buf);
		if(!frame.valid)
		{
			fprintf(stderr, "Invalid frame!\n");
			frame.dump(stderr);
			continue;
		}

		if(writeout != NULL)
			frame.write(writeout);

		if(debug)
			ubx_dump_any(frame, stderr);

		ubx_nav_pvt pvt(frame);
		if(pvt.valid)
		{
			stats.period_pvt++;
			if(pvt.data.fixType >= 2) stats.period_fix++;
			current_pvt = pvt;
			if(!quiet) print_status_line(pvt);
		}

		ubx_nav_eoe eoe(frame);
		if(eoe.valid)
		{
			if(eoe.iTOW != current_pvt.data.iTOW)
			{
				fprintf(stderr, "\nEOE iTOW mismatch! %u != %u\n", eoe.iTOW, last_pvt.data.iTOW);
			}

			if(!quiet) fputs(" EOE", stderr);

			if((writeout == NULL || current_pvt.data.day != last_pvt.data.day) && !no_write)
			{
				if(writeout != NULL)
					fclose(writeout);
				char dirname[64];
				if(current_pvt.data.month != last_pvt.data.month)
				{
					snprintf(dirname, 64, "%04u-%02hhu", current_pvt.data.year, current_pvt.data.month);
					if(mkdir(dirname, 0755) != 0)
					{
						if(errno != EEXIST)
						{
							perror(dirname);
							RETURN_ERR;
						}
					}
					if(!quiet)
						fprintf(stderr, "\nCreated directory %s\n", dirname);
				}
				char filename[128];
				snprintf(filename, 128, "%s/%04u%02hhu%02hhuT%02hhu%02hhu%02hhu.ubx",
					dirname,
					current_pvt.data.year, current_pvt.data.month, current_pvt.data.day, current_pvt.data.hour, current_pvt.data.min, current_pvt.data.sec);
				writeout = fopen(filename, "wb");
				if(writeout == NULL)
				{
					fprintf(stderr, "Unable to open file %s!\n", filename);
					RETURN_ERR;
				}
				if(!quiet)
					fprintf(stderr, "\nOpened file %s\n", filename);
			}

			last_pvt = current_pvt;
		}

		stats.period_bytes += 8 + frame.length;
		stats.period_frames++;

		time_t now = time(NULL);
		if(now >= stats_next)
		{
			print_stats(stats, now);
			stats_next = now + 60;
		}
	}

	if(!quiet)
		fputs("\nEOF!?\n", stderr);
	return 0;
}