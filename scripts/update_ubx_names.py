#!/usr/bin/env python3
"""
Parse UBX message types from the u-blox interface description markdown
and generate updated rawlogger/ubx_names.cpp.

Usage:
    python3 scripts/update_ubx_names.py
"""

import re
import os
from collections import OrderedDict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MD_PATH = os.path.join(PROJECT_DIR, "docs", "u-blox-F9-HPG-1.51_InterfaceDescription_UBXDOC-963802114-13124.md")
CPP_PATH = os.path.join(PROJECT_DIR, "rawlogger", "ubx_names.cpp")


def parse_markdown(path):
    """Extract all UBX-XXX-YYY (0xCC 0xMM) entries from the markdown doc."""
    entries = {}  # class_name -> {msg_id_hex_str: msg_name}

    pattern = re.compile(
        r'UBX-([A-Z0-9]+)-([A-Z0-9]+)\s+\(0x([0-9a-f]{2})\s+0x([0-9a-f]{2})\)',
        re.IGNORECASE
    )

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    for match in pattern.finditer(content):
        class_name = match.group(1)
        msg_name = match.group(2)
        class_id = match.group(3)    # hex string, e.g. "01"
        msg_id = match.group(4)      # hex string, e.g. "22"

        if class_name not in entries:
            entries[class_name] = OrderedDict()
        entries[class_name][msg_id] = msg_name

    # Sort each sub-map by msg_id numerically
    for class_name in entries:
        entries[class_name] = OrderedDict(
            sorted(entries[class_name].items(), key=lambda x: int(x[0], 16))
        )

    return entries


def format_hex(hex_str):
    """Format hex string as C hex literal, e.g. '01' -> '0x01'"""
    return f"0x{hex_str}"


def format_name_map(table, indent=1):
    """Format a C++ initializer list for ubx_name_map_t."""
    prefix = "\t" * indent
    lines = []
    for hex_id, name in table.items():
        lines.append(f'{prefix}{{{format_hex(hex_id)}, "{name}"}}')
    return ",\n".join(lines)


def generate_cpp(entries):
    """Generate the complete ubx_names.cpp content."""

    # Class ID to name mapping (from the markdown doc)
    class_name_map = OrderedDict()
    # These class IDs are known from the doc
    known_class_ids = {
        "01": "NAV", "02": "RXM", "04": "INF", "05": "ACK",
        "06": "CFG", "09": "UPD", "0a": "MON", "0d": "TIM",
        "13": "MGA", "21": "LOG", "27": "SEC", "29": "NAV2",
    }
    for hex_id, name in sorted(known_class_ids.items(), key=lambda x: int(x[0], 16)):
        class_name_map[hex_id] = name

    # Generate sub-maps for each class
    sub_maps = {}
    for class_name, msgs in entries.items():
        sub_maps[class_name] = msgs

    # Build the C++ code
    lines = []
    lines.append('#include "ubx.hpp"')
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("using std::map;")
    lines.append("")
    lines.append("// UBX Class/Message IDs")
    lines.append("static ubx_name_map_t ubx_class_names =")
    lines.append("{")

    class_entries = []
    for hex_id, name in class_name_map.items():
        class_entries.append(f'\t{{{format_hex(hex_id)}, "{name}"}}')
    lines.append(",\n".join(class_entries))

    lines.append("};")
    lines.append("")

    # Generate all sub-maps in a consistent order
    sub_map_order = [
        ("ACK", "ubx_ack_names"),
        ("CFG", "ubx_cfg_names"),
        ("INF", "ubx_inf_names"),
        ("LOG", "ubx_log_names"),
        ("MGA", "ubx_mga_names"),
        ("MON", "ubx_mon_names"),
        ("NAV", "ubx_nav_names"),
        ("NAV2", "ubx_nav2_names"),
        ("RXM", "ubx_rxm_names"),
        ("SEC", "ubx_sec_names"),
        ("TIM", "ubx_tim_names"),
        ("UPD", "ubx_upd_names"),
    ]

    for class_name, var_name in sub_map_order:
        if class_name in sub_maps:
            lines.append(f"static ubx_name_map_t {var_name} =")
            lines.append("{")
            lines.append(format_name_map(sub_maps[class_name]))
            lines.append("};")
            lines.append("")

    # Generate the ubx_names map linking class names to sub-maps
    lines.append("static map<string, ubx_name_map_t> ubx_names =")
    lines.append("{")
    map_entries = []
    for class_name, var_name in sub_map_order:
        if class_name in sub_maps:
            map_entries.append(f'\t{{"{class_name}", {var_name}}}')
    lines.append(",\n".join(map_entries))
    lines.append("};")
    lines.append("")

    # ubx_msg_name function
    lines.append('''string ubx_msg_name(uint8_t class_id, uint8_t msg_id)
{
\tstring class_name;
\tstring msg_name;
\tchar buf[32];
\tif(ubx_class_names.count(class_id) == 0) // unknown class
\t{
\t\tsnprintf(buf, sizeof(buf), "%#02x-%#02x", class_id, msg_id);
\t\treturn string(buf);
\t}
\telse
\t{
\t\tclass_name = ubx_class_names[class_id];
\t}

\tif(ubx_names[class_name].count(msg_id) == 0) // known class, unknown msg
\t{
\t\tsnprintf(buf, sizeof(buf), "%#02x", msg_id);
\t\tmsg_name = buf;
\t}
\telse // known class, known msg
\t{
\t\tmsg_name = ubx_names[class_name][msg_id];
\t}
\treturn class_name + "-" + msg_name;
}
''')

    # GNSS ID maps
    lines.append('''// u-blox GNSS id
static ubx_name_map_t ubx_gnssid_names =
{
\t{0, "GPS"},
\t{1, "SBAS"},
\t{2, "GAL"},
\t{3, "BDS"},
\t{4, "IMES"},
\t{5, "QZSS"},
\t{6, "GLO"},
\t{7, "NavIC"}
};

static ubx_name_map_t ubx_gnssid_abbr_names =
{
\t{0, "G"},
\t{1, "S"},
\t{2, "E"},
\t{3, "B"},
\t{4, "I"},
\t{5, "Q"},
\t{6, "R"},
\t{7, "N"}
};

string ubx_gnssid_name(uint8_t gnssid)
{
\tif(ubx_gnssid_names.count(gnssid) == 0)
\t{
\t\treturn "?";
\t}
\treturn ubx_gnssid_names[gnssid];
}

string ubx_gnssid_abbr_name(uint8_t gnssid)
{
\tif(ubx_gnssid_abbr_names.count(gnssid) == 0)
\t{
\t\treturn "?";
\t}
\treturn ubx_gnssid_abbr_names[gnssid];
}
''')

    lines.append("} // namespace UBX")
    # Add trailing newline
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"Parsing: {MD_PATH}")
    entries = parse_markdown(MD_PATH)

    total_msgs = sum(len(msgs) for msgs in entries.values())
    print(f"Found {len(entries)} UBX classes with {total_msgs} message types:")
    for class_name in sorted(entries.keys()):
        msgs = entries[class_name]
        print(f"  {class_name}: {len(msgs)} messages")

    cpp_content = generate_cpp(entries)

    print(f"\nWriting: {CPP_PATH}")
    with open(CPP_PATH, 'w', encoding='utf-8') as f:
        f.write(cpp_content)

    print("Done.")


if __name__ == "__main__":
    main()