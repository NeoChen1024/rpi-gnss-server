#include <cstdint>
#include <stdio.h>
#include "ubx.hpp"
#include <endian.h>

namespace UBX
{
using std::string;

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
// TODO: make it more elegant
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

ubx_any_msg::ubx_any_msg()
{
	clear();
}

ubx_any_msg::ubx_any_msg(ubx_frame &frame)
{
	parse(frame);
}

void ubx_any_msg::clear()
{
	this->valid = false;
	this->class_id = 0;
	this->msg_id = 0;
	this->payload.clear();
}

bool ubx_any_msg::parse(ubx_frame &frame)
{
	if(frame.valid == false)
	{
		return false;
	}

	this->class_id = frame.class_id;
	this->msg_id = frame.msg_id;
	this->payload = frame.payload;
	return true;
}

void ubx_any_msg::dump(FILE *fp)
{
	fprintf(fp, "%s (%zd)\t> ",
		("UBX-" + ubx_msg_name(this->class_id, this->msg_id)).c_str(),
		this->payload.size());
	for(auto i: this->payload)
	{
		fprintf(fp, "%02x", i);
	}
	fprintf(fp, "\n");
}

} // namespace UBX