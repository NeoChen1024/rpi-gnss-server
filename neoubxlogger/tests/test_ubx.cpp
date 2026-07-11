#include "ubx.hpp"

#include <cassert>
#include <cstdio>
#include <cstring>

using namespace UBX;

int main()
{
	const ubx_buf_t bytes = {0xff, 0xfe, 0xfd, 0xfc, 0xfb, 0xfa, 0xf9, 0xf8};
	assert(read_le<uint16_t>(bytes, 0) == 0xfeffu);
	assert(read_le<uint32_t>(bytes, 0) == 0xfcfdfeffu);
	assert(read_le<int16_t>(bytes, 0) == -257);
	assert(read_le<int32_t>(bytes, 0) == -50462977);
	assert(read_le<uint64_t>(bytes, 0) == UINT64_C(0xf8f9fafbfcfdfeff));
	const ubx_buf_t float_bytes = {0x00, 0x00, 0x80, 0x3f};
	assert(read_le<float>(float_bytes, 0) == 1.0f);
	bool threw = false;
	try
	{
		(void)read_le<uint32_t>(float_bytes, 1);
	}
	catch(const std::out_of_range &)
	{
		threw = true;
	}
	assert(threw);

	// Zero-length payloads are legal UBX frames. The buffer excludes sync bytes.
	ubx_buf_t raw = {0x01, 0x02, 0x00, 0x00, 0x03, 0x0a};
	const ubx_frame frame(raw);
	assert(frame.valid);
	assert(frame.payload.empty());

	ubx_any_msg message(frame);
	assert(message.valid);

	ubx_nav_pvt pvt;
	pvt.valid = true; // Simulate successful structural decoding.
	pvt.data.valid = 0x03;
	pvt.data.month = 13;
	assert(!ubx_nav_pvt_semantically_valid(pvt));
	assert(pvt.valid); // Semantic rejection must not rewrite parser validity.
	pvt.data.month = 7;
	pvt.data.day = 11;
	pvt.data.fixType = 3;
	assert(ubx_nav_pvt_semantically_valid(pvt));
	assert(ubx_nav_pvt_fix_type(pvt) == "3D");

	FILE *fp = tmpfile();
	assert(fp != NULL);
	assert(frame.write(fp) == 0);
	rewind(fp);
	unsigned char written[8] = {};
	assert(fread(written, 1, sizeof(written), fp) == sizeof(written));
	const unsigned char expected[] = {0xb5, 0x62, 0x01, 0x02, 0x00, 0x00, 0x03, 0x0a};
	assert(memcmp(written, expected, sizeof(expected)) == 0);
	fclose(fp);

	return 0;
}
