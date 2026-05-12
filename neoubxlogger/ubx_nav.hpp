// SPDX-License-Identifier: BSD-3-Clause
// Copyright (c) 2026, Kelei Chen

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
};
