#include "ubx_def.hpp"

#pragma once

namespace UBX
{
string ubx_msg_name(uint8_t class_id, uint8_t msg_id);
string ubx_gnssid_name(uint8_t gnssid);
string ubx_gnssid_abbr_name(uint8_t gnssid);
} // namespace UBX