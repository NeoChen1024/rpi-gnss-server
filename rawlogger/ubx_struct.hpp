#include <cstddef>
#include <cstdint>
#include <stdint.h>
#include <vector>
#include "ubx_def.hpp"

#pragma once

namespace UBX
{
using std::vector;

constexpr size_t UBX_NAV_PVT_SIZE = 92;

// UBX-NAV-PVT
struct _ubx_nav_pvt
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

struct _ubx_nav_sig_data
{
	uint8_t gnssId;
	uint8_t svId;
	uint8_t sigId;
	uint8_t freqId; // GLONASS, -7 for real frequency slot number
	int16_t prRes;	// unit = 0.1m
	uint8_t cno;	// dbHz
	uint8_t qualityInd;
	uint8_t corrSource;
	uint8_t ionoModel;
	uint16_t sigFlags;
	uint8_t reserved1[4];
} __attribute((packed));

} // namespace UBX
