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
}