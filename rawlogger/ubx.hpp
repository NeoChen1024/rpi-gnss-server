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
#include "ubx_nav.hpp"

#pragma once

namespace UBX
{
using std::vector;
using std::map;
using std::string;

string ubx_msg_name(uint8_t class_id, uint8_t msg_id);
string ubx_gnssid_name(uint8_t gnssid);
string ubx_gnssid_abbr_name(uint8_t gnssid);

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