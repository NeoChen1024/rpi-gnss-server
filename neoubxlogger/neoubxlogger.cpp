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
#include <format>

#define RETURN_ERR \
	return 1

using namespace UBX;

enum class ReadResult
{
	ok,
	end,
	timeout,
	error,
};

struct ByteReadResult
{
	ReadResult result;
	uint8_t byte = 0;
};

using read_byte_fn = ByteReadResult (*)(void *context);

static ByteReadResult file_read_byte(void *context)
{
	FILE *fp = static_cast<FILE *>(context);
	int c = fgetc(fp);
	if(c != EOF)
		return {.result = ReadResult::ok, .byte = static_cast<uint8_t>(c)};
	return {.result = feof(fp) ? ReadResult::end : ReadResult::error};
}

static ByteReadResult tcp_read_byte(void *context)
{
	int fd = *static_cast<int *>(context);
	unsigned char c;
	while(true)
	{
		ssize_t n = read(fd, &c, 1);
		if(n == 1) return {.result = ReadResult::ok, .byte = c};
		if(n == 0) return {.result = ReadResult::end};
		if(errno == EINTR) continue;
		if(errno == EAGAIN || errno == EWOULDBLOCK)
			return {.result = ReadResult::timeout};
		return {.result = ReadResult::error};
	}
}

static ReadResult read_ubx_frame(void *context, read_byte_fn read_byte, ubx_buf_t &buf)
{
	bool have_sync1 = false;
	size_t wasted_bytes = 0;

	while(true)
	{
		auto read_result = read_byte(context);
		if(read_result.result != ReadResult::ok) return read_result.result;
		uint8_t c = read_result.byte;
		if(!have_sync1)
		{
			have_sync1 = c == UBX_SYNC1;
			if(!have_sync1) wasted_bytes++;
			continue;
		}
		if(c == UBX_SYNC2) break;

		// The previous SYNC1 was noise. Retain a new SYNC1 so B5 B5 62
		// resynchronizes at the second byte instead of dropping the frame.
		wasted_bytes++;
		have_sync1 = c == UBX_SYNC1;
		if(!have_sync1) wasted_bytes++;
	}

	buf.clear();
	if(wasted_bytes > 0)
		fprintf(stderr, "read_ubx_frame(): WASTED %zd Bytes\n", wasted_bytes);

	for(size_t i = 0; i < UBX_HEADER_SIZE; i++)
	{
		auto read_result = read_byte(context);
		if(read_result.result != ReadResult::ok) return read_result.result;
		buf.push_back(read_result.byte);
	}

	size_t length = size_t(buf[UBX_LENGTH_OFFSET]) |
		(size_t(buf[UBX_LENGTH_OFFSET + 1]) << 8);
	for(size_t i = 0; i < length + UBX_CKSUM_SIZE; i++)
	{
		auto read_result = read_byte(context);
		if(read_result.result != ReadResult::ok) return read_result.result;
		buf.push_back(read_result.byte);
	}
	return ReadResult::ok;
}

void print_status_line(const ubx_nav_pvt &pvt)
{
	char buf[128];
	fputc('\r', stderr);
	for(int i = 0; i < 80; i++)
		buf[i] = ' ';
	buf[80] = '\0';
	fputs(buf, stderr);
	auto status = std::format("\riTOW={:06}.{:03} {:>10} {:04}/{:02}/{:02} {:02}:{:02}:{:02}, Sats: {:02}",
		pvt.data.iTOW / 1000, pvt.data.iTOW % 1000,
		ubx_nav_pvt_fix_type(pvt).c_str(),
		pvt.data.year, pvt.data.month, pvt.data.day, pvt.data.hour, pvt.data.min, pvt.data.second,
		pvt.data.numSV);
	fputs(status.c_str(), stderr);
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

		struct timeval tv = {.tv_sec = 5, .tv_usec = 0};
		setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

		if(connect(sockfd, rp->ai_addr, rp->ai_addrlen) == 0)
			break;
		close(sockfd);
		sockfd = -1;
	}

	freeaddrinfo(res);
	return sockfd;
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
		auto message = std::format(
			"\n[neoubxlogger stats] avg rate: {:.1f} KiB/s, frames: {}, FIX {}%\n",
			rate, st.period_frames, pct);
		fputs(message.c_str(), stderr);
	}
	else
	{
		auto message = std::format(
			"\n[neoubxlogger stats] avg rate: {:.1f} KiB/s, frames: {}, FIX ---%\n",
			rate, st.period_frames);
		fputs(message.c_str(), stderr);
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

	Stats stats{.last_print = time(NULL)};

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

	while(1)
	{
		ubx_buf_t buf;

		if(tcp_mode)
		{
			ReadResult ret = read_ubx_frame(&sockfd, tcp_read_byte, buf);
			if(ret == ReadResult::timeout)
				continue;
			if(ret != ReadResult::ok)
			{
				if(ret == ReadResult::error) perror("TCP read");
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
			ReadResult ret = read_ubx_frame(readin, file_read_byte, buf);
			if(ret == ReadResult::end) break;
			if(ret != ReadResult::ok)
			{
				perror("UBX input");
				RETURN_ERR;
			}
		}

		ubx_frame frame(buf);
		if(!frame.valid)
		{
			fprintf(stderr, "Invalid frame!\n");
			frame.dump(stderr);
			continue;
		}

		if(writeout != NULL && frame.write(writeout) == EOF)
		{
			perror("UBX output");
			RETURN_ERR;
		}

		if(debug && !ubx_nav_dump_custom(frame, stderr))
			ubx_dump_any(frame, stderr);

		ubx_nav_pvt pvt(frame);
		if(ubx_nav_pvt_semantically_valid(pvt))
		{
			stats.period_pvt++;
			if(pvt.data.fixType >= 2) stats.period_fix++;
			current_pvt = pvt;
			if(!quiet) print_status_line(pvt);
		}

		ubx_nav_eoe eoe(frame);
		if(ubx_nav_eoe_semantically_valid(eoe))
		{
			if(!current_pvt.valid)
			{
				fprintf(stderr, "\nIgnoring NAV-EOE without a valid NAV-PVT\n");
			}
			else
			{
				if(eoe.data.iTOW != current_pvt.data.iTOW)
				{
					fprintf(stderr, "\nEOE iTOW mismatch! %u != %u\n", eoe.data.iTOW, current_pvt.data.iTOW);
				}

				if(!quiet) fputs(" EOE", stderr);

				if((writeout == NULL || current_pvt.data.day != last_pvt.data.day) && !no_write)
				{
					if(writeout != NULL)
						fclose(writeout);
					char dirname[64];
					snprintf(dirname, sizeof(dirname), "%04u-%02hhu",
						current_pvt.data.year, current_pvt.data.month);
					if(mkdir(dirname, 0755) != 0 && errno != EEXIST)
					{
						perror(dirname);
						RETURN_ERR;
					}
					char filename[128];
					snprintf(filename, 128, "%s/%04u%02hhu%02hhuT%02hhu%02hhu%02hhu.ubx",
						dirname,
						current_pvt.data.year, current_pvt.data.month, current_pvt.data.day, current_pvt.data.hour, current_pvt.data.min, current_pvt.data.second);
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
