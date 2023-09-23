#include "ubx.hpp"

namespace UBX
{
ubx_nav_pvt::ubx_nav_pvt()
{
	clear();
}

ubx_nav_pvt::ubx_nav_pvt(ubx_frame &frame)
{
	parse(frame);
}

void ubx_nav_pvt::clear()
{
	memset(&this->data, 0, sizeof(this->data));
	this->valid = false;
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

bool ubx_nav_pvt::parse(ubx_frame &frame)
{
	this->valid = false;
	if(frame.valid == false)
	{
		return false;
	}
	if(ubx_msg_name(frame.class_id, frame.msg_id) != std::string("NAV-PVT"))
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