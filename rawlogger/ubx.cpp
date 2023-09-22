#include <stdio.h>
#include "ubx.hpp"
#include <endian.h>

namespace UBX
{
using std::string;
using std::vector;
using std::map;

// UBX IDs
map<uint8_t, string> ubx_class_names =
{
	{0x01, "NAV"},
	{0x02, "RXM"},
	{0x0A, "MON"},
};

map<uint8_t, string> ubx_mon_names =
{
	{0x38, "RF"},
	{}
};

map<uint8_t, string> ubx_nav_names =
{
	{0x07, "PVT"},
	{0x35, "ODO"},
	{0x61, "EOE"},
	{0x35, "SAT"},
	{0x43, "SIG"},
	{0x32, "SBAS"}
};

map<uint8_t, string> ubx_rxm_names =
{
	{0x14, "MEASX"},
	{0x15, "RAWX"},
	{0x13, "SRFBX"}
};

uint8_t getu1(ubx_buf_t &buf, size_t offset)
{
	return buf.at(offset);
}

uint16_t getu2(ubx_buf_t &buf, size_t offset)
{
	return buf.at(offset) | (buf.at(offset + 1) << 8);
}

uint32_t getu4(ubx_buf_t &buf, size_t offset)
{
	return
		 buf.at(offset) |
		(buf.at(offset + 1) << 8) |
		(buf.at(offset + 2) << 16) |
		(buf.at(offset + 3) << 24);
}

int8_t geti1(ubx_buf_t &buf, size_t offset)
{
	return buf.at(offset);
}

int16_t geti2(ubx_buf_t &buf, size_t offset)
{
	return buf.at(offset) | (buf.at(offset + 1) << 8);
}

int32_t geti4(ubx_buf_t &buf, size_t offset)
{
	return
		 buf.at(offset) |
		(buf.at(offset + 1) << 8) |
		(buf.at(offset + 2) << 16) |
		(buf.at(offset + 3) << 24);
}

float getr4(ubx_buf_t &buf, size_t offset)
{
	uint32_t tmp = getu4(buf, offset);
	return *(float *)&tmp;
}

double getr8(ubx_buf_t &buf, size_t offset)
{
	uint64_t tmp = getu4(buf, offset) | ((uint64_t)getu4(buf, offset + 4) << 32);
	return *(double *)&tmp;
}

uint8_t getch(ubx_buf_t &buf, size_t offset)
{
	return getu1(buf, offset);
}

void ubx_frame::clear()
{
	this->valid = false;
	this->class_id = 0;
	this->msg_id = 0;
	this->length = 0;
	this->payload.clear();
	this->cksum = 0;
}

ubx_frame::ubx_frame()
{
	clear();
}

ubx_frame::ubx_frame(ubx_buf_t &buf)
{
	clear();
	if (buf.size() < 8)
	{
		return;
	}
	this->class_id = buf[UBX_CLASS_OFFSET];
	this->msg_id = buf[UBX_MSG_OFFSET];
	this->length = buf[UBX_LENGTH_OFFSET] | (buf[UBX_LENGTH_OFFSET + 1] << 8);
	this->cksum = (buf[buf.size() - 2]<<8) | buf[buf.size() - 1];
	if(validate(buf))
	{
		this->valid = true;
	}
	this->payload = ubx_buf_t(buf.begin() + UBX_HEADER_SIZE, buf.end() - UBX_CKSUM_SIZE);
}

bool ubx_frame::validate(ubx_buf_t &buf)
{
	if(buf.size() < 8)
	{
		fputs("ubx_frame::validate(): buf.size() < 8\n", stderr);
		return false;
	}
	if(buf.size() != (size_t)this->length + UBX_HEADER_SIZE + UBX_CKSUM_SIZE)
	{
		fprintf(stderr, "ubx_frame::validate(): buf.size() = %zd, length = %d\n", buf.size(), this->length);
		return false;
	}
	uint8_t ck_a = 0, ck_b = 0;
	for (size_t i = 0; i < buf.size() - 2; i++)
	{
		ck_a += buf[i];
		ck_b += ck_a;
	}
	uint16_t buf_cksum = (ck_a << 8) | ck_b;
	if(buf_cksum != this->cksum)
	{
		fprintf(stderr, "ubx_frame::validate(): buf_cksum = %04x, cksum = %04x\n", buf_cksum, this->cksum);
		return false;
	}

	return true;
}

void ubx_frame::dump(FILE *fp)
{
	fprintf(fp, "=========\n");
	fprintf(fp, "class_id: %02x\n", this->class_id);
	fprintf(fp, "msg_id: %02x\n", this->msg_id);
	fprintf(fp, "length: %d\n", this->length);
	fprintf(fp, "cksum: %04x\n", this->cksum);
	fprintf(fp, "buf: ");
	for (unsigned int i = 0; i < this->payload.size(); i++)
	{
		fprintf(fp, "%02x ", this->payload[i]);
	}
	fprintf(fp, "\n");
	fprintf(fp, "valid: %d\n", this->valid);
}

// Returns EOF on error
int ubx_frame::write(FILE *fp)
{
	int ret = 0;
	ret |= fputc(UBX_SYNC1, fp);
	ret |= fputc(UBX_SYNC2, fp);
	ret |= fputc(this->class_id, fp);
	ret |= fputc(this->msg_id, fp);
	ret |= fputc(this->length & 0xff, fp);
	ret |= fputc((this->length >> 8) & 0xff, fp);
	for(size_t i = 0; i < this->payload.size(); i++)
	{
		ret |= fputc(this->payload[i], fp);
	}
	ret |= fputc(this->cksum >> 8, fp);
	ret |= fputc(this->cksum & 0xff, fp);
	return ret;
}

void ubx_nav_pvt::clear()
{
	memset(&this->data, 0, sizeof(this->data));
	this->valid = false;
}

ubx_nav_pvt::ubx_nav_pvt()
{
	clear();
}

bool ubx_nav_pvt::validate()
{
	if(data.month < 1 || data.month > 12)
	{
		return false;
	}
	if(data.day < 1 || data.day > 31)
	{
		return false;
	}
	if(data.hour > 23)
	{
		return false;
	}
	if(data.min > 59)
	{
		return false;
	}
	// leap second is 60
	if(data.sec > 60)
	{
		return false;
	}
	return true;
}

ubx_nav_pvt::ubx_nav_pvt(ubx_frame &frame)
{
	parse(frame);
}

bool ubx_nav_pvt::parse(ubx_frame &frame)
{
	// Clear all fields
	clear();
	if(frame.valid == false)
	{
		return false;
	}
	if(frame.class_id != UBX_CLASS_NAV || frame.msg_id != UBX_NAV_PVT)
	{
		return false; // ignore non NAV-PVT frames
	}
	assert(sizeof(this->data) == UBX_NAV_PVT_SIZE);
	if(frame.length != sizeof(this->data))
	{
		fprintf(stderr, "ubx_nav_pvt::ubx_nav_pvt(): frame.length = %d, sizeof(this->data) = %zd\n", frame.length, sizeof(this->data));
		return false;
	}
	memcpy(&this->data, frame.payload.data(), sizeof(this->data));
	// Endianness conversion
	data.iTOW = le32toh(data.iTOW);
	data.year = le16toh(data.year);
	data.tAcc = le32toh(data.tAcc);
	data.nano = le32toh(data.nano);
	data.lon = le32toh(data.lon);
	data.lat = le32toh(data.lat);
	data.height = le32toh(data.height);
	data.hMSL = le32toh(data.hMSL);
	data.hAcc = le32toh(data.hAcc);
	data.vAcc = le32toh(data.vAcc);
	data.velN = le32toh(data.velN);
	data.velE = le32toh(data.velE);
	data.velD = le32toh(data.velD);
	data.gSpeed = le32toh(data.gSpeed);
	data.headMot = le32toh(data.headMot);
	data.sAcc = le32toh(data.sAcc);
	data.headAcc = le32toh(data.headAcc);
	data.pDOP = le16toh(data.pDOP);
	data.headVeh = le32toh(data.headVeh);
	if(validate())
	{
		this->valid = true;
		return true;
	}
	else
	{
		return false;
	}
}

void ubx_nav_pvt::dump(FILE *fp)
{
	fputs("=====================\n", fp);
	fprintf(fp, "iTOW: %u\n", data.iTOW);
	fprintf(fp, "Date: %04u/%02hhu/%02hhu %02hhu:%02hhu:%02hhu\n",
		data.year, data.month, data.day, data.hour, data.min, data.sec);
	fprintf(fp, "valid: %u\n", data.valid);
	fprintf(fp, "tAcc: %u\n", data.tAcc);
	fprintf(fp, "nano: %d\n", data.nano);
	fprintf(fp, "fixType: %u\n", data.fixType);
	fprintf(fp, "flags: %u\n", data.flags);
	fprintf(fp, "flags2: %u\n", data.flags2);
	fprintf(fp, "numSV: %u\n", data.numSV);
	fprintf(fp, "lon: %d, lat: %d\n", data.lon, data.lat);
	fprintf(fp, "height: %d, hMSL: %d\n", data.height, data.hMSL);
	fprintf(fp, "hAcc: %u, vAcc: %u\n", data.hAcc, data.vAcc);
	fprintf(fp, "velN/E/D: %d/%d/%d\n", data.velN, data.velE, data.velD);
	fprintf(fp, "gSpeed: %d\n", data.gSpeed);
	fprintf(fp, "headMot: %d\n", data.headMot);
	fprintf(fp, "sAcc: %u\n", data.sAcc);
	fprintf(fp, "headAcc: %u\n", data.headAcc);
	fprintf(fp, "pDOP: %u\n", data.pDOP);
	fprintf(fp, "headVeh: %d\n", data.headVeh);
}

} // namespace UBX