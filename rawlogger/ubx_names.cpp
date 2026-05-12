#include "ubx.hpp"

namespace UBX
{
using std::map;

// UBX Class/Message IDs
static ubx_name_map_t ubx_class_names =
{
	{0x01, "NAV"},
	{0x02, "RXM"},
	{0x04, "INF"},
	{0x05, "ACK"},
	{0x06, "CFG"},
	{0x09, "UPD"},
	{0x0a, "MON"},
	{0x0d, "TIM"},
	{0x13, "MGA"},
	{0x21, "LOG"},
	{0x27, "SEC"},
	{0x29, "NAV2"}
};

static ubx_name_map_t ubx_ack_names =
{
	{0x00, "NAK"},
	{0x01, "ACK"}
};

static ubx_name_map_t ubx_cfg_names =
{
	{0x00, "PRT"},
	{0x01, "MSG"},
	{0x02, "INF"},
	{0x04, "RST"},
	{0x06, "DAT"},
	{0x08, "RATE"},
	{0x09, "CFG"},
	{0x13, "ANT"},
	{0x16, "SBAS"},
	{0x17, "NMEA"},
	{0x1b, "USB"},
	{0x1e, "ODO"},
	{0x23, "NAVX5"},
	{0x24, "NAV5"},
	{0x31, "TP5"},
	{0x34, "RINV"},
	{0x3e, "GNSS"},
	{0x47, "LOGFILTER"},
	{0x57, "PWR"},
	{0x69, "GEOFENCE"},
	{0x70, "DGNSS"},
	{0x71, "TMODE3"},
	{0x8a, "VALSET"},
	{0x8b, "VALGET"},
	{0x8c, "VALDEL"}
};

static ubx_name_map_t ubx_inf_names =
{
	{0x00, "ERROR"},
	{0x01, "WARNING"},
	{0x02, "NOTICE"},
	{0x03, "TEST"},
	{0x04, "DEBUG"}
};

static ubx_name_map_t ubx_log_names =
{
	{0x03, "ERASE"},
	{0x04, "STRING"},
	{0x07, "CREATE"},
	{0x08, "INFO"},
	{0x09, "RETRIEVE"},
	{0x0b, "RETRIEVEPOS"},
	{0x0d, "RETRIEVESTRING"},
	{0x0e, "FINDTIME"},
	{0x0f, "RETRIEVEPOSEXTRA"}
};

static ubx_name_map_t ubx_mga_names =
{
	{0x00, "GPS"},
	{0x02, "GAL"},
	{0x03, "BDS"},
	{0x05, "QZSS"},
	{0x06, "GLO"},
	{0x40, "INI"},
	{0x60, "ACK"},
	{0x80, "DBD"}
};

static ubx_name_map_t ubx_mon_names =
{
	{0x02, "IO"},
	{0x04, "VER"},
	{0x06, "MSGPP"},
	{0x07, "RXBUF"},
	{0x08, "TXBUF"},
	{0x09, "HW"},
	{0x0b, "HW2"},
	{0x21, "RXR"},
	{0x27, "PATCH"},
	{0x28, "GNSS"},
	{0x31, "SPAN"},
	{0x36, "COMMS"},
	{0x37, "HW3"},
	{0x38, "RF"},
	{0x39, "SYS"}
};

static ubx_name_map_t ubx_nav_names =
{
	{0x01, "POSECEF"},
	{0x02, "POSLLH"},
	{0x03, "STATUS"},
	{0x04, "DOP"},
	{0x07, "PVT"},
	{0x09, "ODO"},
	{0x10, "RESETODO"},
	{0x11, "VELECEF"},
	{0x12, "VELNED"},
	{0x13, "HPPOSECEF"},
	{0x14, "HPPOSLLH"},
	{0x20, "TIMEGPS"},
	{0x21, "TIMEUTC"},
	{0x22, "CLOCK"},
	{0x23, "TIMEGLO"},
	{0x24, "TIMEBDS"},
	{0x25, "TIMEGAL"},
	{0x26, "TIMELS"},
	{0x27, "TIMEQZSS"},
	{0x32, "SBAS"},
	{0x34, "ORB"},
	{0x35, "SAT"},
	{0x36, "COV"},
	{0x39, "GEOFENCE"},
	{0x3b, "SVIN"},
	{0x3c, "RELPOSNED"},
	{0x42, "SLAS"},
	{0x43, "SIG"},
	{0x61, "EOE"},
	{0x62, "PL"},
	{0x64, "TIMETRUSTED"}
};

static ubx_name_map_t ubx_nav2_names =
{
	{0x01, "POSECEF"},
	{0x02, "POSLLH"},
	{0x03, "STATUS"},
	{0x04, "DOP"},
	{0x07, "PVT"},
	{0x09, "ODO"},
	{0x11, "VELECEF"},
	{0x12, "VELNED"},
	{0x20, "TIMEGPS"},
	{0x21, "TIMEUTC"},
	{0x22, "CLOCK"},
	{0x23, "TIMEGLO"},
	{0x24, "TIMEBDS"},
	{0x25, "TIMEGAL"},
	{0x26, "TIMELS"},
	{0x27, "TIMEQZSS"},
	{0x32, "SBAS"},
	{0x35, "SAT"},
	{0x36, "COV"},
	{0x3b, "SVIN"},
	{0x42, "SLAS"},
	{0x43, "SIG"},
	{0x61, "EOE"}
};

static ubx_name_map_t ubx_rxm_names =
{
	{0x13, "SFRBX"},
	{0x14, "MEASX"},
	{0x15, "RAWX"},
	{0x32, "RTCM"},
	{0x33, "SPARTN"},
	{0x34, "COR"},
	{0x36, "SPARTNKEY"},
	{0x41, "PMREQ"},
	{0x59, "RLM"},
	{0x72, "PMP"},
	{0x73, "QZSSL6"}
};

static ubx_name_map_t ubx_sec_names =
{
	{0x03, "UNIQID"},
	{0x09, "SIG"},
	{0x0a, "OSNMA"},
	{0x10, "SIGLOG"}
};

static ubx_name_map_t ubx_tim_names =
{
	{0x01, "TP"},
	{0x03, "TM2"},
	{0x06, "VRFY"}
};

static ubx_name_map_t ubx_upd_names =
{
	{0x14, "SOS"}
};

static map<string, ubx_name_map_t> ubx_names =
{
	{"ACK", ubx_ack_names},
	{"CFG", ubx_cfg_names},
	{"INF", ubx_inf_names},
	{"LOG", ubx_log_names},
	{"MGA", ubx_mga_names},
	{"MON", ubx_mon_names},
	{"NAV", ubx_nav_names},
	{"NAV2", ubx_nav2_names},
	{"RXM", ubx_rxm_names},
	{"SEC", ubx_sec_names},
	{"TIM", ubx_tim_names},
	{"UPD", ubx_upd_names}
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

// u-blox GNSS id
static ubx_name_map_t ubx_gnssid_names =
{
	{0, "GPS"},
	{1, "SBAS"},
	{2, "GAL"},
	{3, "BDS"},
	{4, "IMES"},
	{5, "QZSS"},
	{6, "GLO"},
	{7, "NavIC"}
};

static ubx_name_map_t ubx_gnssid_abbr_names =
{
	{0, "G"},
	{1, "S"},
	{2, "E"},
	{3, "B"},
	{4, "I"},
	{5, "Q"},
	{6, "R"},
	{7, "N"}
};

string ubx_gnssid_name(uint8_t gnssid)
{
	if(ubx_gnssid_names.count(gnssid) == 0)
	{
		return "?";
	}
	return ubx_gnssid_names[gnssid];
}

string ubx_gnssid_abbr_name(uint8_t gnssid)
{
	if(ubx_gnssid_abbr_names.count(gnssid) == 0)
	{
		return "?";
	}
	return ubx_gnssid_abbr_names[gnssid];
}

} // namespace UBX
