#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <cstddef>
#include <vector>
#include <map>
#include <string>

#include "ubx_def.hpp"
#include "ubx_struct.hpp"

#pragma once

namespace UBX
{
using std::vector;
using std::map;
using std::string;

string ubx_msg_name(uint8_t class_id, uint8_t msg_id);
string ubx_gnssid_name(uint8_t gnssid);
string ubx_gnssid_abbr_name(uint8_t gnssid);

class ubx_frame
{
public:
	uint8_t class_id;
	uint8_t msg_id;
	uint16_t length;
	ubx_buf_t payload;
	// CK_A is high byte, CK_B is low byte
	uint16_t cksum;

	bool valid;

	ubx_frame();
	ubx_frame(ubx_buf_t &buf);
	void clear();
	void dump(FILE *fp);
	int write(FILE *fp);
private:
	bool validate(ubx_buf_t &buf);
};

class ubx_any_msg
{
public:
	bool valid;
	uint8_t class_id;
	uint8_t msg_id;
	ubx_buf_t payload;

	ubx_any_msg();
	ubx_any_msg(ubx_frame &frame);
	bool parse(ubx_frame &frame);
	void clear();
	void dump(FILE *fp);
};

class ubx_nav_pvt : public ubx_any_msg
{
public:
	struct _ubx_nav_pvt data;
	bool valid;

	ubx_nav_pvt();
	ubx_nav_pvt(ubx_frame &frame);
	bool parse(ubx_frame &frame);
	void clear();
	void dump(FILE *fp);
private:
	bool validate();
};

// x1 x2 x4 -> u1 u2 u4

uint8_t getu1(ubx_buf_t &buf, size_t offset);
uint16_t getu2(ubx_buf_t &buf, size_t offset);
uint32_t getu4(ubx_buf_t &buf, size_t offset);
int8_t geti1(ubx_buf_t &buf, size_t offset);
int16_t geti2(ubx_buf_t &buf, size_t offset);
int32_t geti4(ubx_buf_t &buf, size_t offset);
float getr4(ubx_buf_t &buf, size_t offset);
double getr8(ubx_buf_t &buf, size_t offset);
uint8_t getch(ubx_buf_t &buf, size_t offset);


} // namespace UBX