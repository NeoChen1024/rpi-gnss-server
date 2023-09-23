#include "ubx.hpp"

namespace UBX
{
using std::map;

// UBX IDs
ubx_name_map_t ubx_class_names =
{
	{0x01, "NAV"},
	{0x02, "RXM"},
	{0x04, "INF"},
	{0x05, "ACK"},
	{0x06, "CFG"},
	{0x09, "UPD"},
	{0x0A, "MON"},
	{0x0D, "TIM"},
	{0x13, "MGA"},
	{0x21, "LOG"},
	{0x27, "SEC"}
};

ubx_name_map_t ubx_mon_names =
{
	{0x36, "COMMS"},
	{0x28, "GNSS"},
	{0x0B, "HW2"},
	{0x37, "HW3"},
	{0x09, "HW"},
	{0x02, "IO"},
	{0x06, "MSGPP"},
	{0x27, "PATCH"},
	{0x38, "RF"},
	{0x07, "RXBUF"},
	{0x21, "RXR"},
	{0x08, "TXBUF"},
	{0x31, "SPAN"},
	{0x04, "VER"},
	{0x39, "SYS"} // not in u-blox documentation, but u-center has support for it
};

ubx_name_map_t ubx_nav_names =
{
	{0x22, "CLOCK"},
	{0x04, "DOP"},
	{0x36, "COV"},
	{0x61, "EOE"},
	{0x39, "GEOFENCE"},
	{0x13, "HPPOSECEF"},
	{0x14, "HPPOSLLH"},
	{0x09, "ODO"},
	{0x34, "ORB"},
	{0x01, "POSECEF"},
	{0x02, "POSLLH"},
	{0x07, "PVT"},
	{0x3C, "RELPOSNED"},
	{0x35, "SAT"},
	{0x43, "SIG"},
	{0x42, "SLAS"},
	{0x03, "STATUS"},
	{0x3B, "SVIN"},
	{0x24, "TIMEBDS"},
	{0x25, "TIMEGAL"},
	{0x23, "TIMEGLO"},
	{0x20, "TIMEGPS"},
	{0x27, "TIMEQZSS"},
	{0x26, "TIMELS"},
	{0x21, "TIMEUTC"},
	{0x11, "VELECEF"},
	{0x12, "VELNED"},
	{0x32, "SBAS"}
};

ubx_name_map_t ubx_rxm_names =
{
	{0x14, "MEASX"},
	{0x15, "RAWX"},
	{0x32, "RTCM"},
	{0x13, "SRFBX"}
};

ubx_name_map_t ubx_tim_names =
{
	{0x01, "TP"},
	{0x03, "TM2"},
	{0x06, "VRFY"}
};

ubx_name_map_t ubx_sec_names =
{
	{0x03, "UNIQID"},
	{0x09, "SIG"}, // not in u-blox documentation, but u-center has support for it
	{0x10, "SIGLOG"} // same as above
};

map<string, ubx_name_map_t> ubx_names =
{
	{"MON", ubx_mon_names},
	{"NAV", ubx_nav_names},
	{"RXM", ubx_rxm_names},
	{"TIM", ubx_tim_names},
	{"SEC", ubx_sec_names}
};

string ubx_msg_name(uint8_t class_id, uint8_t msg_id)
{
	string class_name;
	string msg_name;
	char buf[32];
	if(ubx_class_names.count(class_id) == 0) // unknown class
	{
		snprintf(buf, sizeof(buf), "%#02x-%#02x", class_id, msg_id);
		return string(buf);
	}
	else
	{
		class_name = ubx_class_names[class_id];
	}

	if(ubx_names[class_name].count(msg_id) == 0) // known class, unknown msg
	{
		snprintf(buf, sizeof(buf), "%#02x", msg_id);
		msg_name = buf;
	}
	else // known class, known msg
	{
		msg_name = ubx_names[class_name][msg_id];
	}
	return class_name + "-" + msg_name;
}

} // namespace UBX