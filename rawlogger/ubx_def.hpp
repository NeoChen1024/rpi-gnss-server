#include <string>
#include <vector>
#include <map>
#include <cstddef>
#include <stdint.h>

#pragma once

namespace UBX
{
using std::vector;
using std::map;
using std::string;

constexpr uint8_t UBX_SYNC1	= 0xB5;
constexpr uint8_t UBX_SYNC2	= 0x62;
constexpr uint8_t UBX_CLASS_OFFSET	= 0;
constexpr uint8_t UBX_MSG_OFFSET	= 1;
constexpr uint8_t UBX_LENGTH_OFFSET	= 2;
constexpr uint8_t UBX_HEADER_SIZE	= 4;
constexpr uint8_t UBX_CKSUM_SIZE	= 2;

constexpr uint8_t UBX_CLASS_NAV	= 0x01;
constexpr uint8_t UBX_CLASS_RXM	= 0x02;
constexpr uint8_t UBX_CLASS_MON	= 0x0A;
constexpr uint8_t UBX_NAV_PVT	= 0x07;
constexpr uint8_t UBX_RXM_RAWX	= 0x15;
constexpr uint8_t UBX_RXM_SRFBX	= 0x13;

typedef vector<uint8_t> ubx_buf_t;
typedef map<uint8_t, string> ubx_name_map_t;

class ubx_frame;
} // namespace UBX