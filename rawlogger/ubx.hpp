#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <vector>
#include <map>
#include <string>

#include "ubx_struct.hpp"

namespace UBX
{
using std::vector;

constexpr uint8_t UBX_SYNC1	= 0xB5;
constexpr uint8_t UBX_SYNC2	= 0x62;
constexpr uint8_t UBX_CLASS_OFFSET = 0;
constexpr uint8_t UBX_MSG_OFFSET = 1;
constexpr uint8_t UBX_LENGTH_OFFSET = 2;
constexpr uint8_t UBX_HEADER_SIZE	= 4;
constexpr uint8_t UBX_CKSUM_SIZE	= 2;

constexpr uint8_t UBX_CLASS_NAV	= 0x01;
constexpr uint8_t UBX_CLASS_RXM	= 0x02;
constexpr uint8_t UBX_CLASS_MON	= 0x0A;
constexpr uint8_t UBX_NAV_PVT	= 0x07;
constexpr uint8_t UBX_RXM_RAWX	= 0x15;
constexpr uint8_t UBX_RXM_SRFBX	= 0x13;

typedef vector<uint8_t> ubx_buf_t;

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

class ubx_nav_pvt
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