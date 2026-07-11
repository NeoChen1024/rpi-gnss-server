#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Kelei Chen

"""
Generate C++ UBX message parsers (structs + parser classes with endianness conversion)
from pyubx2's Python payload definitions.

Usage:
    python3 scripts/generate_ubx_parsers.py

Output:
    neoubxlogger/ubx_struct_gen.hpp  - Packed struct definitions
    neoubxlogger/ubx_{class}_gen.hpp  - Parser class declarations (one per UBX class)
    neoubxlogger/ubx_{class}_gen.cpp  - Parser implementations
"""

import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAWLOGGER_DIR = os.path.join(PROJECT_DIR, "neoubxlogger")

# Path to pyubx2 types modules
PYUBX2_DIR = os.path.join(PROJECT_DIR, "3rdparty", "pyubx2", "src")
sys.path.insert(0, PYUBX2_DIR)

TARGET_CLASSES = ("NAV", "RXM", "MON", "TIM", "ESF", "HNR", "LOG", "SEC", "CFG", "ACK")
SKIP_MESSAGES = {"FOO-BAR"}


@dataclass
class BitFieldInfo:
    name: str
    bits: int


@dataclass
class FieldInfo:
    name: str
    pytype: str | None = None
    ctype: str = "uint8_t"
    arr_size: int = 0
    size: int = 0
    is_scaled: bool = False
    is_bitfield: bool = False
    is_repeating: bool = False
    is_reserved: bool = False
    scale_factor: Any = None
    bit_fields: list[BitFieldInfo] = field(default_factory=list)
    repeat_count: int | str | None = None
    nested_fields: list["FieldInfo"] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Type mapping: Python type string -> C++ type
# ---------------------------------------------------------------------------

# Base type (no array suffix) for each pytype prefix
BASE_TYPE_MAP = {
    "U": "uint8_t",
    "I": "int8_t",
    "R": "float",   # R4=float, R8=double - overridden below
    "X": "uint8_t",
    "C": "uint8_t",  # char/byte array
    "A": "uint8_t",  # byte array
    "L": "uint8_t",
    "E": "uint8_t",
}

SPECIAL_TYPES = {
    "R004": "float",
    "R008": "double",
    "X008": "uint64_t",
    "E002": "uint16_t",
    "E004": "uint32_t",
}

ENDIAN_SCALAR_TYPES = {
    "U002", "U004", "U008", "I002", "I004", "I008",
    "E002", "E004", "X002", "X004", "X008", "R004", "R008",
}

X_HEX_WIDTH = {
    "X001": 2,
    "X002": 4,
    "X004": 8,
    "X008": 16,
}

# ---------------------------------------------------------------------------
# Type info
# ---------------------------------------------------------------------------

def parse_pytype(pytype: str) -> dict:
    """Parse a pytype string like 'U004', 'C030', 'R008' into base type info."""
    m = re.match(r'([UIRXCAEL])(\d{3})', pytype)
    if not m:
        return {"base_type": "uint8_t", "size": 1, "is_array": False}
    prefix = m.group(1)
    sz = int(m.group(2))

    if pytype in SPECIAL_TYPES:
        base = SPECIAL_TYPES[pytype]
        is_array = False
    elif prefix == "R" and sz == 8:
        base = "double"
        is_array = False
    elif sz <= 8 and prefix in ("U", "I", "X", "E"):
        size_map = {
            ("U", 1): "uint8_t", ("U", 2): "uint16_t", ("U", 4): "uint32_t", ("U", 8): "uint64_t",
            ("I", 1): "int8_t",  ("I", 2): "int16_t",  ("I", 4): "int32_t",  ("I", 8): "int64_t",
            ("X", 1): "uint8_t", ("X", 2): "uint16_t", ("X", 4): "uint32_t", ("X", 8): "uint64_t",
            ("E", 1): "uint8_t", ("E", 2): "uint16_t", ("E", 4): "uint32_t",
        }
        if (prefix, sz) in size_map:
            base = size_map[(prefix, sz)]
            is_array = False
        else:
            # e.g. U003, U005, U006, U007, X006 - no native C type, use byte array
            base = BASE_TYPE_MAP.get(prefix, "uint8_t")
            is_array = True
    else:
        base = BASE_TYPE_MAP.get(prefix, "uint8_t")
        is_array = sz > 1 or prefix in ("C", "A", "E") or sz > 8

    return {"base_type": base, "size": sz, "is_array": is_array}


def get_c_type_decl(pytype: str) -> str:
    """Get C++ type declaration (only the type part, no name)."""
    info = parse_pytype(pytype)
    if info["is_array"]:
        return info["base_type"]
    return info["base_type"]

def get_field_size(pytype: str) -> int:
    info = parse_pytype(pytype)
    return info["size"]

def is_array_type(pytype: str) -> bool:
    if pytype is None:
        return False
    info = parse_pytype(pytype)
    return info["is_array"]

def cpp_field_decl(ctype: str, name: str, arr_size: int = 0) -> str:
    """Emit `type name;` or `type name[size];`"""
    if arr_size > 0:
        return f"{ctype} {name}[{arr_size}];"
    return f"{ctype} {name};"

def find_bitfield_subfield(fields: list[FieldInfo], subfield_name):
    """Find a bitfield containing a named sub-field and return its C++ extraction expression.
    Returns None if not found in any bitfield."""
    for f in fields:
        if f.is_bitfield and f.bit_fields:
            offset = 0
            for bf in f.bit_fields:
                if bf.name == subfield_name:
                    bits = bf.bits
                    total_bits = f.size * 8
                    if offset == 0 and bits == total_bits:
                        return f"this->{f.name}"
                    elif bits <= 31:
                        mask = (1 << bits) - 1
                        return f"((int)((this->{f.name} >> {offset}) & 0x{mask:x}))"
                    else:
                        return f"this->{f.name}"
                offset += bf.bits
    return None

# ---------------------------------------------------------------------------
# Payload definition parser
# ---------------------------------------------------------------------------

def parse_payload_def(payload_def: dict) -> list[FieldInfo]:
    """
    Parse a UBX_PAYLOADS_GET payload definition into a flat list of fields.
    """
    fields = []
    for field_name, field_type in payload_def.items():
        info = FieldInfo(
            name=field_name,
            is_reserved=bool(re.match(r'reserved\d*', field_name)),
        )

        if isinstance(field_type, str):
            info.pytype = field_type
            info.ctype = get_c_type_decl(field_type)
            info.size = get_field_size(field_type)
            info.arr_size = info.size if is_array_type(field_type) else 0

        elif isinstance(field_type, list):
            raw_type = field_type[0]
            scale = field_type[1]
            info.pytype = raw_type
            info.ctype = get_c_type_decl(raw_type)
            info.size = get_field_size(raw_type)
            info.arr_size = info.size if is_array_type(raw_type) else 0
            info.is_scaled = True
            info.scale_factor = scale

        elif isinstance(field_type, tuple):
            numr = field_type[0]
            nested = field_type[1]

            if isinstance(numr, str) and numr.startswith("X"):
                info.is_bitfield = True
                info.pytype = numr
                info.ctype = get_c_type_decl(numr)
                info.size = get_field_size(numr)
                info.arr_size = info.size if is_array_type(numr) else 0
                for k, v in nested.items():
                    m = re.match(r'[UXI](\d+)', str(v))
                    info.bit_fields.append(BitFieldInfo(k, int(m.group(1)) if m else 1))
            else:
                info.is_repeating = True
                info.nested_fields = parse_payload_def(nested)
                info.repeat_count = numr
                info.size = sum(f.size for f in info.nested_fields)
        else:
            raise TypeError(f"Unknown field type {type(field_type)} for {field_name}: {field_type!r}")

        fields.append(info)
    return fields


def is_fixed_size(fields):
    for f in fields:
        if f.is_repeating:
            rc = f.repeat_count
            if rc is None or rc == "None" or isinstance(rc, str):
                return False
    return True

def compute_struct_size(fields):
    total = 0
    for f in fields:
        if f.is_repeating:
            rc = f.repeat_count
            if isinstance(rc, int):
                total += f.size * rc
            else:
                return 0
        else:
            total += f.size
    return total

# ---------------------------------------------------------------------------
# Name helpers
# ---------------------------------------------------------------------------

def struct_name(msg_name):
    return "_ubx_" + msg_name.lower().replace("-", "_")

def parser_class_name(msg_name):
    return "ubx_" + msg_name.lower().replace("-", "_")

def msg_id_const(msg_name):
    return "UBX_" + "_".join(p.upper() for p in msg_name.split("-"))

def class_id_const(cls: str):
    return "UBX_CLASS_" + cls.upper()


def is_generated_msg_name(msg_name):
    return msg_name not in SKIP_MESSAGES and not msg_name.startswith("UBX-")


def should_generate_parser(msg_name, ubx_payloads):
    return msg_name in ubx_payloads and is_generated_msg_name(msg_name)


def should_generate_struct(msg_name, ubx_payloads):
    return should_generate_parser(msg_name, ubx_payloads)


def should_generate_dump_case(msg_name, ubx_payloads):
    return msg_name in ubx_payloads and is_generated_msg_name(msg_name)


def write_output(path, content):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            if f.read() == content:
                print(f"Unchanged: {path}")
                return

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Wrote: {path}")

# ---------------------------------------------------------------------------
# Struct generation
# ---------------------------------------------------------------------------

def gen_struct_inner(fields, struct_tag, indent=1):
    """Generate the body of a packed struct. Returns list of lines."""
    lines = []
    tab = "\t" * indent
    for f in fields:
        if f.is_repeating and isinstance(f.repeat_count, int):
            inner_name = f"{struct_tag}_{f.name}"
            lines.append(f"{tab}// {f.name} x {f.repeat_count}")
            lines.append(f"{tab}struct {inner_name}")
            lines.append(f"{tab}{{")
            for nf in f.nested_fields:
                if nf.is_repeating and isinstance(nf.repeat_count, int):
                    inner2_name = f"{inner_name}_{nf.name}"
                    lines.append(f"{tab}\tstruct {inner2_name}")
                    lines.append(f"{tab}\t{{")
                    for nf2 in nf.nested_fields:
                        lines.append(f"{tab}\t\t{cpp_field_decl(nf2.ctype, nf2.name, nf2.arr_size)}")
                    lines.append(f"{tab}\t}} {nf.name}[{nf.repeat_count}];")
                else:
                    lines.append(f"{tab}\t{cpp_field_decl(nf.ctype, nf.name, nf.arr_size)}")
            lines.append(f"{tab}}} {f.name}[{f.repeat_count}];")
        elif f.is_repeating:
            pass  # variable repeating group - skip in struct
        else:
            lines.append(f"{tab}{cpp_field_decl(f.ctype, f.name, f.arr_size)}")
    return lines


def generate_struct(msg_name, fields):
    struct = struct_name(msg_name)
    sz = compute_struct_size(fields)
    lines = []
    lines.append(f"// {msg_name}")
    lines.append(f"struct {struct}")
    lines.append("{")
    lines.extend(gen_struct_inner(fields, struct, 1))
    lines.append("} __attribute__((packed));")
    lines.append("")
    if sz > 0:
        lines.append(f"static_assert(sizeof({struct}) == {sz}, \"{struct} size mismatch\");")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser class header
# ---------------------------------------------------------------------------

def generate_parser_header(msg_name, fields, ubx_class):
    cls = parser_class_name(msg_name)
    struct = struct_name(msg_name)
    fixed = is_fixed_size(fields) and compute_struct_size(fields) > 0

    lines = []
    lines.append(f"class {cls} : public ubx_any_msg")
    lines.append("{")
    lines.append("public:")
    if fixed:
        lines.append(f"\tstruct {struct} data;")
    else:
        # Declare scalar/array fields for variable-size messages
        for f in fields:
            if f.is_repeating:
                continue
            decl = cpp_field_decl(f.ctype, f.name, f.arr_size)
            lines.append(f"\t{decl}")

    # Variable repeating group -> vector
    has_vector = False
    for f in fields:
        if f.is_repeating and not isinstance(f.repeat_count, int):
            nest_struct = f"{struct}_{f.name}_t"
            lines.append(f"\tstruct {nest_struct}")
            lines.append("\t{")
            for nf in f.nested_fields:
                if nf.is_repeating and isinstance(nf.repeat_count, int):
                    inner_inner = f"{nest_struct}_{nf.name}"
                    lines.append(f"\t\tstruct {inner_inner}")
                    lines.append("\t\t{")
                    for nf2 in nf.nested_fields:
                        lines.append(f"\t\t\t{cpp_field_decl(nf2.ctype, nf2.name, nf2.arr_size)}")
                    lines.append(f"\t\t}} {nf.name}[{nf.repeat_count}];")
                else:
                    lines.append(f"\t\t{cpp_field_decl(nf.ctype, nf.name, nf.arr_size)}")
            lines.append(f"\t}};")
            lines.append(f"\tvector<{nest_struct}> {f.name};")
            has_vector = True
    # Fixed repeating groups in variable-size messages -> struct array
    if not fixed:
        for f in fields:
            if f.is_repeating and isinstance(f.repeat_count, int):
                inner_name = f"{struct}_{f.name}"
                lines.append(f"\tstruct {inner_name}")
                lines.append("\t{")
                for nf in f.nested_fields:
                    lines.append(f"\t\t{cpp_field_decl(nf.ctype, nf.name, nf.arr_size)}")
                lines.append(f"\t}} {f.name}[{f.repeat_count}];")

    if has_vector and not fixed:
        lines.append("")

    lines.append("")
    lines.append(f"\t{cls}();")
    lines.append(f"\t{cls}(const ubx_frame &frame);")
    lines.append(f"\tbool parse(const ubx_frame &frame);")
    lines.append(f"\tvoid clear();")
    lines.append(f"\tvoid dump(FILE *fp) const;")
    lines.append("")
    lines.append("private:")
    lines.append("\tbool validate();")
    lines.append("};")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parser implementation
# ---------------------------------------------------------------------------

def is_multi_byte_scalar(f):
    """Check if a field is a multi-byte scalar (needs endian conversion)."""
    if f.is_repeating or f.is_reserved:
        return False
    if not f.pytype:
        return False
    if is_array_type(f.pytype):
        return False
    if f.size <= 1:
        return False
    return f.size in (2, 4, 8)


def needs_endian_field(f):
    return is_multi_byte_scalar(f) and f.pytype[:4] in ENDIAN_SCALAR_TYPES


def gen_read_field(f, prefix, tab):
    """Generate bounds-checked code to read one scalar/array field."""
    lines = [
        f"{tab}if(off > frame.length || size_t({f.size}) > frame.length - off)",
        f"{tab}{{",
        f'{tab}\treport_parse_error(std::format("field {f.name} at offset {{}} exceeds payload length {{}}", off, frame.length));',
        f"{tab}\treturn false;",
        f"{tab}}}",
    ]

    if not is_array_type(f.pytype):
        lines.append(f"{tab}{prefix}{f.name} = read_le<{f.ctype}>(frame.payload, off);")
    else:
        sz = f.size
        lines.append(f"{tab}memcpy(&{prefix}{f.name}, frame.payload.data() + off, {sz});")

    lines.append(f"{tab}off += {f.size};")
    return lines


def generate_parser_impl(msg_name, fields, ubx_class):
    cls = parser_class_name(msg_name)
    struct = struct_name(msg_name)
    fixed = is_fixed_size(fields) and compute_struct_size(fields) > 0
    total_sz = compute_struct_size(fields)

    lines = []

    # Constructor
    lines.append(f"{cls}::{cls}() {{ clear(); }}")
    lines.append("")
    lines.append(f"{cls}::{cls}(const ubx_frame &frame) {{ parse(frame); }}")
    lines.append("")

    # clear()
    lines.append(f"void {cls}::clear()")
    lines.append("{")
    if fixed:
        lines.append("\tmemset(&this->data, 0, sizeof(this->data));")
    else:
        for f in fields:
            if f.is_repeating and not isinstance(f.repeat_count, int):
                continue  # handled below
            if f.is_repeating:
                lines.append(f"\tmemset(&this->{f.name}, 0, sizeof(this->{f.name}));")
                continue
            if f.pytype is None:
                continue
            pt = f.pytype
            if is_array_type(pt):
                lines.append(f"\tmemset(&this->{f.name}, 0, sizeof(this->{f.name}));")
            else:
                lines.append(f"\tthis->{f.name} = 0;")
    for f in fields:
        if f.is_repeating and not isinstance(f.repeat_count, int):
            lines.append(f"\tthis->{f.name}.clear();")
    lines.append("\tthis->valid = false;")
    lines.append("}")
    lines.append("")

    # parse()
    lines.append(f"bool {cls}::parse(const ubx_frame &frame)")
    lines.append("{")
    lines.append("\tthis->clear();")
    lines.append("\tif(!frame.valid) return false;")
    lines.append("")
    cc = class_id_const(ubx_class)
    mc = msg_id_const(msg_name)
    lines.append(f"\tif(frame.class_id != {cc} || frame.msg_id != {mc}) return false;")
    lines.append("")

    if fixed and total_sz > 0:
        lines.append(f"\tif(frame.length != sizeof(this->data))")
        lines.append("\t{")
        lines.append(f'\t\treport_parse_error(std::format("{cls}: length {{}} != expected {{}}", frame.length, sizeof(this->data)));')
        lines.append("\t\treturn false;")
        lines.append("\t}")
        lines.append("")
        lines.append("\tmemcpy(&this->data, frame.payload.data(), sizeof(this->data));")
        lines.append("")

        # Endianness for top-level multi-byte scalars (not reserved, not arrays)
        scalar_conv = [(f"data.{f.name}", f.pytype) for f in fields
                       if needs_endian_field(f)]
        if scalar_conv:
            lines.append("\t// Endianness conversion")
            for path, pt in scalar_conv:
                lines.append(f"\t{path} = little_to_native({path});")

        # Fixed repeating groups with endianness
        for f in fields:
            if f.is_repeating and isinstance(f.repeat_count, int):
                conv_nf = [nf for nf in f.nested_fields if needs_endian_field(nf)]
                conv_nested_rg = [nf for nf in f.nested_fields
                                  if nf.is_repeating and isinstance(nf.repeat_count, int)]
                if conv_nf:
                    lines.append(f"\tfor(int i = 0; i < {f.repeat_count}; i++)")
                    lines.append("\t{")
                    for nf in conv_nf:
                        lines.append(f"\t\tdata.{f.name}[i].{nf.name} = little_to_native(data.{f.name}[i].{nf.name});")
                    lines.append("\t}")
                if conv_nested_rg:
                    for nf in conv_nested_rg:
                        conv_nf2 = [nf2 for nf2 in nf.nested_fields if needs_endian_field(nf2)]
                        if conv_nf2:
                            lines.append(f"\tfor(int i = 0; i < {f.repeat_count}; i++)")
                            lines.append("\t{")
                            lines.append(f"\t\tfor(int j = 0; j < {nf.repeat_count}; j++)")
                            lines.append("\t\t{")
                            for nf2 in conv_nf2:
                                lines.append(f"\t\t\tdata.{f.name}[i].{nf.name}[j].{nf2.name} = little_to_native(data.{f.name}[i].{nf.name}[j].{nf2.name});")
                            lines.append("\t\t}")
                            lines.append("\t}")
    else:
        # Field-by-field parsing for variable-size messages
        lines.append("\tsize_t off = 0;")
        lines.append("")
        for f in fields:
            if f.is_repeating:
                rc = f.repeat_count
                elem_sz = f.size
                if not elem_sz:
                    elem_sz = sum(g.size for g in f.nested_fields)
                nest_type = f"{struct}_{f.name}_t"

                if rc == "None" or rc is None:
                    lines.append(f"\t// repeating group: {f.name}")
                    lines.append(f"\twhile(off + {elem_sz} <= frame.length)")
                    lines.append("\t{")
                    lines.append(f"\t\t{nest_type} item;")
                    lines.extend(gen_read_fields(f.nested_fields, "item.", "\t\t"))
                    lines.append(f"\t\tthis->{f.name}.push_back(item);")
                    lines.append("\t}")
                elif isinstance(rc, str):
                    # Repeat count may be a top-level field or a bitfield sub-field
                    count_expr = find_bitfield_subfield(fields, rc)
                    if count_expr is None:
                        count_expr = f"this->{rc}"
                    lines.append(f"\t// repeating group: {f.name} x {count_expr}")
                    lines.append(f"\tfor(int i = 0; i < {count_expr}; i++)")
                    lines.append("\t{")
                    lines.append(f"\t\t{nest_type} item;")
                    lines.extend(gen_read_fields(f.nested_fields, "item.", "\t\t"))
                    lines.append(f"\t\tthis->{f.name}.push_back(item);")
                    lines.append("\t}")
                elif isinstance(rc, int):
                    lines.append(f"\t// fixed repeating group: {f.name} x {rc}")
                    lines.append(f"\tfor(int i = 0; i < {rc}; i++)")
                    lines.append("\t{")
                    lines.extend(gen_read_fields(f.nested_fields, f"this->{f.name}[i].", "\t\t"))
                    lines.append("\t}")
            elif f.is_bitfield:
                lines.extend(gen_read_field(f, "this->", "\t"))
            else:
                lines.extend(gen_read_field(f, "this->", "\t"))

    lines.append("")
    if not fixed:
        lines.append("\tif(off != frame.length) return false;")
        lines.append("")
    lines.append("\tif(validate()) { this->valid = true; return true; }")
    lines.append("\telse { return false; }")
    lines.append("}")
    lines.append("")

    # validate()
    lines.append(f"bool {cls}::validate()")
    lines.append("{")
    lines.append("\t// TODO: add validation if needed")
    lines.append("\treturn true;")
    lines.append("}")
    lines.append("")

    # dump()
    lines.append(f"void {cls}::dump(FILE *fp) const")
    lines.append("{")
    lines.append(f'\tstd::string output = "({msg_name}";')
    if fixed:
        for f in fields:
            if f.is_reserved:
                continue
            if f.is_repeating and isinstance(f.repeat_count, int):
                lines.append(f'\toutput += std::format(", {f.name}={{}} items x {{}} bytes", {f.repeat_count}, {f.size});')
            elif not f.is_repeating and f.pytype:
                pt = f.pytype[:4]
                if is_array_type(f.pytype):
                    lines.append(f'\toutput += std::format(", {f.name}={{}} bytes", sizeof(data.{f.name}));')
                elif pt.startswith("X"):
                    width = X_HEX_WIDTH.get(pt, 2)
                    lines.append(f'\toutput += std::format(", {f.name}=0x{{:0{width}x}}", +data.{f.name});')
                else:
                    lines.append(f'\toutput += std::format(", {f.name}={{}}", +data.{f.name});')
    else:
        for f in fields:
            if f.is_reserved:
                continue
            if f.is_repeating and not isinstance(f.repeat_count, int):
                lines.append(f'\toutput += std::format(", {f.name}={{}} items", this->{f.name}.size());')
            elif f.is_repeating and isinstance(f.repeat_count, int):
                continue
            elif not f.is_repeating and f.pytype:
                pt = f.pytype[:4]
                if is_array_type(f.pytype):
                    lines.append(f'\toutput += std::format(", {f.name}={{}} bytes", sizeof(this->{f.name}));')
                elif pt.startswith("X"):
                    width = X_HEX_WIDTH.get(pt, 2)
                    lines.append(f'\toutput += std::format(", {f.name}=0x{{:0{width}x}}", +this->{f.name});')
                else:
                    lines.append(f'\toutput += std::format(", {f.name}={{}}", +this->{f.name});')
    lines.append('\toutput += ")\\n";')
    lines.append('\tfputs(output.c_str(), fp);')
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def gen_read_fields(fields, prefix, tab):
    """Generate code to read fields from payload at offset `off`."""
    lines = []
    for f in fields:
        if f.is_repeating and isinstance(f.repeat_count, int):
            lines.append(f"{tab}// nested fixed rg {f.name} x {f.repeat_count}")
            lines.append(f"{tab}for(int j = 0; j < {f.repeat_count}; j++)")
            lines.append(f"{tab}{{")
            lines.extend(gen_read_fields(f.nested_fields, f"{prefix}{f.name}[j].", tab + "\t"))
            lines.append(f"{tab}}}")
        else:
            lines.extend(gen_read_field(f, prefix, tab))
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def get_interesting_classes():
    from pyubx2.ubxtypes_core import UBX_CLASSES, UBX_MSGIDS
    from pyubx2.ubxtypes_get import UBX_PAYLOADS_GET

    msg_to_ids = {}
    for key, name in UBX_MSGIDS.items():
        if len(key) == 2:
            msg_to_ids[name] = (key[0], key[1])

    classes = OrderedDict()
    for msg_name in sorted(UBX_PAYLOADS_GET.keys()):
        if msg_name in msg_to_ids:
            cls_id, msg_id = msg_to_ids[msg_name]
            cls_name = UBX_CLASSES.get(bytes([cls_id]), f"C_{cls_id:02x}")
            base = cls_name.split("-")[0]
            if base not in classes:
                classes[base] = []
            classes[base].append((msg_name, cls_id, msg_id))
    return classes


HEADER = """/*
 * Auto-generated UBX message parser definitions.
 * Generated from pyubx2 payload definitions by scripts/generate_ubx_parsers.py.
 *
 * UBX payload definitions derived from pyubx2:
 *   Copyright (c) 2020, semuadin (Steve Smith)
 *   SPDX-License-Identifier: BSD-3-Clause
 *   https://github.com/semuconsulting/pyubx2
 *
 * This file is part of the rpi-gnss-server project.
 * Copyright (c) 2026, Kelei Chen
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *   1. Redistributions of source code must retain the above copyright notice,
 *      this list of conditions and the following disclaimer.
 *   2. Redistributions in binary form must reproduce the above copyright
 *      notice, this list of conditions and the following disclaimer in the
 *      documentation and/or other materials provided with the distribution.
 *   3. Neither the name of the copyright holder nor the names of its
 *      contributors may be used to endorse or promote products derived from
 *      this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

"""


def write_struct_file(class_msgs, ubx_payloads):
    lines = [HEADER]
    lines.append('#include <cstddef>')
    lines.append('#include <cstdint>')
    lines.append('#include <stdint.h>')
    lines.append('#include "ubx_ids_gen.hpp"')
    lines.append("")
    lines.append("#pragma once")
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("")
    for msgs in class_msgs.values():
        for msg_name, _, _ in msgs:
            if not should_generate_struct(msg_name, ubx_payloads):
                continue
            payload = ubx_payloads[msg_name]
            fields = parse_payload_def(payload)
            if is_fixed_size(fields) and compute_struct_size(fields) > 0:
                lines.append(generate_struct(msg_name, fields))
    lines.append("")
    lines.append("} // namespace UBX")
    lines.append("")
    return "\n".join(lines)


def write_parser_file(class_name, msgs, ubx_payloads):
    lines = [HEADER]
    lines.append(f'#ifndef UBX_{class_name.upper()}_GEN_HPP')
    lines.append(f'#define UBX_{class_name.upper()}_GEN_HPP')
    lines.append("")
    lines.append('#include "ubx_def.hpp"')
    lines.append('#include "ubx_struct_gen.hpp"')
    lines.append("#include <vector>")
    lines.append("")
    lines.append("#pragma once")
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("using std::vector;")
    lines.append("")
    for msg_name, _, _ in msgs:
        if not should_generate_parser(msg_name, ubx_payloads):
            continue
        payload = ubx_payloads[msg_name]
        fields = parse_payload_def(payload)
        lines.append(generate_parser_header(msg_name, fields, class_name))
        lines.append("")
    lines.append("} // namespace UBX")
    lines.append("")
    lines.append(f'#endif // UBX_{class_name.upper()}_GEN_HPP')
    lines.append("")
    return "\n".join(lines)


def write_parser_impl_file(class_name, msgs, ubx_payloads):
    fn = f"ubx_{class_name.lower()}_gen"
    lines = [HEADER]
    lines.append(f'#include "{fn}.hpp"')
    lines.append('#include "ubx_ids_gen.hpp"')
    lines.append('#include <string>')
    lines.append('#include <format>')
    lines.append('#include <cstring>')
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("")
    for msg_name, _, _ in msgs:
        if not should_generate_parser(msg_name, ubx_payloads):
            continue
        payload = ubx_payloads[msg_name]
        fields = parse_payload_def(payload)
        lines.append(generate_parser_impl(msg_name, fields, class_name))
        lines.append("")
    lines.append("} // namespace UBX")
    lines.append("")
    return "\n".join(lines)


def write_dump_gen_header():
    lines = [HEADER]
    lines.append("#ifndef UBX_DUMP_GEN_HPP")
    lines.append("#define UBX_DUMP_GEN_HPP")
    lines.append("")
    lines.append('#include "ubx_def.hpp"')
    lines.append("")
    lines.append("#pragma once")
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("void ubx_dump_any(const ubx_frame &frame, FILE *fp);")
    lines.append("} // namespace UBX")
    lines.append("")
    lines.append("#endif // UBX_DUMP_GEN_HPP")
    return "\n".join(lines)


def write_dump_gen_impl(class_msgs, target_classes, ubx_payloads):
    lines = [HEADER]
    lines.append('#include "ubx_dump_gen.hpp"')
    lines.append('#include "ubx_ids_gen.hpp"')
    lines.append("")
    for cls_name in target_classes:
        if cls_name in class_msgs:
            lines.append(f'#include "ubx_{cls_name.lower()}_gen.hpp"')
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("")
    lines.append("void ubx_dump_any(const ubx_frame &frame, FILE *fp)")
    lines.append("{")
    lines.append("    if (!frame.valid)")
    lines.append("        return;")
    lines.append("")
    lines.append("    switch (frame.class_id)")
    lines.append("    {")
    for cls_name in target_classes:
        if cls_name not in class_msgs:
            continue
        msgs = class_msgs[cls_name]
        valid = [(n, c, i) for n, c, i in msgs
                 if should_generate_dump_case(n, ubx_payloads)]
        if not valid:
            continue
        cc = class_id_const(cls_name)
        lines.append(f"    case {cc}:")
        lines.append(f"        switch (frame.msg_id)")
        lines.append(f"        {{")
        for msg_name, _, msg_id in valid:
            mc = msg_id_const(msg_name)
            pc = parser_class_name(msg_name)
            lines.append(f"        case {mc}: {{ {pc} p(frame); p.dump(fp); break; }}")
        lines.append(f"        default:")
        lines.append(f'            fprintf(fp, "  unknown msg 0x%02x\\n", frame.msg_id);')
        lines.append(f"            break;")
        lines.append(f"        }}")
        lines.append(f"        break;")
    lines.append("    default:")
    lines.append('        fprintf(fp, "  unknown class 0x%02x / msg 0x%02x\\n", frame.class_id, frame.msg_id);')
    lines.append("        break;")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    lines.append("} // namespace UBX")
    return "\n".join(lines)


def write_ids_file(class_msgs, target_classes):
    """Generate ubx_ids_gen.hpp with all UBX class/message ID constants."""
    lines = [HEADER]
    lines.append("#ifndef UBX_IDS_GEN_HPP")
    lines.append("#define UBX_IDS_GEN_HPP")
    lines.append("")
    lines.append('#include <cstdint>')
    lines.append("")
    lines.append("#pragma once")
    lines.append("")
    lines.append("namespace UBX")
    lines.append("{")
    lines.append("")
    for cls_name in target_classes:
        if cls_name not in class_msgs:
            continue
        msgs = class_msgs[cls_name]
        cls_id = msgs[0][1]
        cc = class_id_const(cls_name)
        lines.append(f"// class {cls_name}")
        lines.append(f"constexpr uint8_t {cc} = 0x{cls_id:02x};")
        lines.append("")
        for msg_name, _, msg_id in msgs:
            if not is_generated_msg_name(msg_name):
                continue
            mc = msg_id_const(msg_name)
            lines.append(f"constexpr uint8_t {mc} = 0x{msg_id:02x};")
        lines.append("")
    lines.append("} // namespace UBX")
    lines.append("")
    lines.append("#endif // UBX_IDS_GEN_HPP")
    lines.append("")
    return "\n".join(lines)


def main():
    from pyubx2.ubxtypes_get import UBX_PAYLOADS_GET

    class_msgs = get_interesting_classes()
    print(f"Found {len(class_msgs)} classes:")
    for cls_name, msgs in sorted(class_msgs.items()):
        print(f"  {cls_name}: {len(msgs)} messages")

    os.makedirs(RAWLOGGER_DIR, exist_ok=True)

    # Generate ID constants
    ids_content = write_ids_file(class_msgs, TARGET_CLASSES)
    p = os.path.join(RAWLOGGER_DIR, "ubx_ids_gen.hpp")
    write_output(p, ids_content)

    # Generate structs
    struct_content = write_struct_file(class_msgs, UBX_PAYLOADS_GET)
    p = os.path.join(RAWLOGGER_DIR, "ubx_struct_gen.hpp")
    write_output(p, struct_content)

    # Generate parser files for interesting classes
    for cls_name in TARGET_CLASSES:
        if cls_name not in class_msgs:
            continue
        msgs = class_msgs[cls_name]
        # Messages that have hand-written parsers -> skip duplication
        valid = [(n, c, i) for n, c, i in msgs
                 if should_generate_parser(n, UBX_PAYLOADS_GET)]
        if not valid:
            continue

        hpp = write_parser_file(cls_name, valid, UBX_PAYLOADS_GET)
        hp = os.path.join(RAWLOGGER_DIR, f"ubx_{cls_name.lower()}_gen.hpp")
        write_output(hp, hpp)

        cpp = write_parser_impl_file(cls_name, valid, UBX_PAYLOADS_GET)
        cp = os.path.join(RAWLOGGER_DIR, f"ubx_{cls_name.lower()}_gen.cpp")
        write_output(cp, cpp)

    # Generate universal dump function
    dump_hpp = write_dump_gen_header()
    dp = os.path.join(RAWLOGGER_DIR, "ubx_dump_gen.hpp")
    write_output(dp, dump_hpp)

    dump_cpp = write_dump_gen_impl(class_msgs, TARGET_CLASSES, UBX_PAYLOADS_GET)
    dp = os.path.join(RAWLOGGER_DIR, "ubx_dump_gen.cpp")
    write_output(dp, dump_cpp)

    print("\nDone.")


if __name__ == "__main__":
    main()
