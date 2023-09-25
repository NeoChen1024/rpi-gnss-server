#include "ubx_def.hpp"
#include "ubx_struct.hpp"

#pragma once

namespace UBX
{
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
	string get_fix_type();
private:
	bool validate();
};

class ubx_nav_eoe : public ubx_any_msg
{
	public:
	bool valid;
	uint32_t iTOW;

	ubx_nav_eoe();
	ubx_nav_eoe(ubx_frame &frame);
	bool parse(ubx_frame &frame);
	void clear();
	void dump(FILE *fp);
private:
	bool validate();
};

class ubx_nav_sig : public ubx_any_msg
{
public:
// UBX-NAV-SIG header
	uint32_t iTOW;
	uint8_t version;
	uint8_t numSigs;
	// not used
	//uint8_t reserved0[2];
	
	vector<struct _ubx_nav_sig_data> data;
	bool valid;

	ubx_nav_sig();
	ubx_nav_sig(ubx_frame &frame);
	bool parse(ubx_frame &frame);
	void clear();
	void dump(FILE *fp);
private:
	bool validate();
};
}