# rpi-gnss-server — AGENTS.md

## Project structure

- `neoubxlogger/` — C++ logger (hand-written + generated parsers). Entrypoint: `neoubxlogger.cpp`.
- `scripts/` — `generate_ubx_parsers.py` (C++ codegen), `update_ubx_names.py`.
- `3rdparty/pyubx2/` — git submodule; its `src/` is added to `sys.path` at codegen time.
- `docs/` — u-blox F9 interface specification PDFs.
- `daily-ubx.sh` — cron job using `gpspipe -R | xz`.
- `rtkserv.sh` — RTKLib `str2str` NTRIP caster startup.

## neoubxlogger — C++ build

```bash
cd neoubxlogger
make setup    # create .venv + install codegen dependencies (optional preflight)
make          # install missing codegen dependencies + generate + compile + link
make gen      # regenerate parsers only
make clean    # rm binary, .o, all *_gen.* files
```

- C++20, `c++` compiler, `-pedantic -Wall -Wextra`.
- `#DBG` (sanitizers) commented out in Makefile.
- Generated files (`*_gen.*`) have `.gitignore` entries and are auto-rebuilt on `make`.
- Scalar decoding uses `read_le<T>(std::span<const uint8_t>)`, `std::bit_cast`,
  and `std::endian`; generated parsers must use these shared helpers.
- Diagnostics and custom NAV dumps use `std::format`; parser diagnostics use
  `std::source_location` through `report_parse_error()`.

### CLI flags

| Flag | Description |
|------|-------------|
| `-f FILE` | Read from .ubx file (default: stdin) |
| `-t HOST:PORT` | Read from TCP socket (auto-reconnects) |
| `-n` | No write |
| `-d` | Debug — single-line dump every frame |
| `-q` | Quiet daemon — suppresses status line, prints per-minute stats |

`-f`/`-t` and `-d`/`-q` are mutually exclusive.

### Codegen architecture

`scripts/generate_ubx_parsers.py` reads `UBX_PAYLOADS_GET` from `pyubx2` and produces:

- `ubx_ids_gen.hpp` — class/msg ID constants
- `ubx_struct_gen.hpp` — packed structs for fixed-size messages
- `ubx_{class}_gen.{hpp,cpp}` — parser classes (NAV, RXM, MON, TIM, ESF, HNR, LOG, SEC, CFG, ACK)
- `ubx_dump_gen.{hpp,cpp}` — universal `UBX::ubx_dump_any(ubx_frame&, FILE*)`

### Generated parsers and NAV helpers

All supported message structs and parser classes, including NAV-PVT and NAV-EOE,
are generated. `ubx_nav.{hpp,cpp}` contains only application-level free functions:

- NAV-PVT and NAV-EOE semantic validation
- NAV-PVT fix-type formatting
- custom NAV-PVT and NAV-EOE debug dumps

Generated parser `valid` means that frame identity, payload length and structural
decoding succeeded. Semantic validity is checked separately by the NAV helpers.

### TCP reader notes

TCP input (`-t`) uses raw `read()` syscalls (not FILE*) in `ubx_read_frame_tcp()`, with `SO_RCVTIMEO` 5s and automatic reconnection on disconnect. The file/stdin path uses the original `ubx_read_frame(FILE*)`.

### `*_gen.hpp` include order

Generated `.cpp` always includes: `ubx_{class}_gen.hpp`, `ubx_ids_gen.hpp`, `inttypes.h`, `string`, `endian.h`, `cstring`.

### Include order

`ubx.hpp` includes: `ubx_def.hpp`, `ubx_names.hpp`, `ubx_nav.hpp`.
`ubx_def.hpp` includes `ubx_ids_gen.hpp`.
`ubx_nav.hpp` includes `ubx_nav_gen.hpp`.

## Testing

No automated test suite. Manual verification with testdata files:

```bash
cd neoubxlogger && ./neoubxlogger < ../testdata/20241103T000000.ubx
```
