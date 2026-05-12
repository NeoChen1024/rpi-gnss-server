# rpi-gnss-server — AGENTS.md

## Project structure

- `rawlogger/` — C++ logger (hand-written + generated parsers). Entrypoint: `rawlogger.cpp`.
- `pyubxlogger/src/neoubxlogger/` — Python rewrite using `uv`. Entrypoint: `neoubxlogger.cli:main`.
- `scripts/` — `generate_ubx_parsers.py` (C++ codegen), `update_ubx_names.py`.
- `3rdparty/pyubx2/` — git submodule; its `src/` is added to `sys.path` at codegen time.
- `docs/` — u-blox F9 interface specification PDFs.
- `daily-ubx.sh` — cron job using `gpspipe -R | xz`.
- `rtkserv.sh` — RTKLib `str2str` NTRIP caster startup.

## rawlogger — C++ build

```bash
cd rawlogger
make setup    # create .venv + install pyrtcm pynmeagps (one-time)
make          # codegen + compile + link
make gen      # regenerate parsers only
make clean    # rm binary, .o, all *_gen.* files
```

- C++11, `c++` compiler, `-pedantic -Wall -Wextra`.
- `#DBG` (sanitizers) commented out in Makefile.
- Generated files (`*_gen.*`) have `.gitignore` entries and are auto-rebuilt on `make`.

### Codegen architecture

`scripts/generate_ubx_parsers.py` reads `UBX_PAYLOADS_GET` from `pyubx2` and produces:
- `ubx_ids_gen.hpp` — class/msg ID constants
- `ubx_struct_gen.hpp` — packed structs for fixed-size messages
- `ubx_{class}_gen.{hpp,cpp}` — parser classes (NAV, RXM, MON, TIM, ESF, HNR, LOG, SEC, CFG, ACK)
- `ubx_dump_gen.{hpp,cpp}` — universal `UBX::ubx_dump_any(ubx_frame&, FILE*)`

### Hand-written vs generated parsers

`HAND_WRITTEN = {"NAV-PVT", "NAV-EOE"}` — these use hand-coded classes in `ubx_nav.{hpp,cpp}`.
- `ubx_nav_pvt` has `get_fix_type()` (returns "3D", "2D", etc.)
- Both have custom `dump()` matching the generated single-line format.
- Generated code skips HAND_WRITTEN messages (no struct, no parser, no id conflict).
- `ubx_dump_gen.cpp` `#include`s `ubx_nav.hpp` for the two hand-written types.

### `*_gen.hpp` include order

Generated `.cpp` always includes: `ubx_{class}_gen.hpp`, `ubx_ids_gen.hpp`, `inttypes.h`, `string`, `endian.h`, `cstring`.

### Hand-written include order

`ubx.hpp` includes: `ubx_def.hpp`, `ubx_names.hpp`, `ubx_struct.hpp`, `ubx_nav.hpp`.
`ubx_def.hpp` includes `ubx_ids_gen.hpp`.

## pyubxlogger — Python logger

```bash
cd pyubxlogger
uv sync
uv run python -m neoubxlogger -f ../testdata/20241103T000000.ubx -nd
```

## Testing

No automated test suite. Manual verification with testdata files:
```bash
cd rawlogger && ./rawlogger < ../testdata/20241103T000000.ubx
```
