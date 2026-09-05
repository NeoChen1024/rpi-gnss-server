# rpi-gnss-server — AGENTS.md

## Project structure

- `neoubxlogger/` — C++ logger (hand-written + generated parsers). Entrypoint: `neoubxlogger.cpp`.
- `scripts/` — `generate_ubx_parsers.py` (C++ parser and message-name codegen).
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
- `ubx_names_gen.cpp` — class/message names from all of `UBX_CLASSES` and
  `UBX_MSGIDS`, independent of parser support or GET/SET/POLL mode; excludes the
  upstream FOO test fixture. MGA subtype names use payload byte 0. Without a
  payload, return the derived family name (including `MGA-ACK/NAK` for 0x1360).

Scaled fields accept current `(type, scale)` tuples and legacy `[type, scale]`
lists. Generated C++ fields retain raw wire values. Bitfield containers follow
pyubx2 names, e.g. NAV-PVT `valid_bit`, `flags_bit`, and `flags2_bit`.
`ubx_names.cpp` contains only hand-written GNSS display names and abbreviations.
The universal dump falls back to the named raw payload for unsupported messages
or failed structural decoding.

The generator normalizes each selected payload once before writing files. Unknown
wire types, invalid counts/bit widths, forward count references, and unsupported
nested dynamic groups are errors with field paths. Fixed nested groups have
recursive wire-size accounting and declarations; all scalar decoding uses
`read_le`, including fixed messages. Dynamic group counts are bounded by the
remaining payload before reserving vectors.

`VARIANTS` records only wire identity and version/type discriminators; payload
layouts remain in pyubx2. Length-based selection uses normalized schema sizes.
The registry covers CFG-NMEA, NAV-AOPSTATUS/DAHEADING/RELPOSNED, RXM-PMP/RLM,
and SEC-SIG/UNIQID versions. New unmatched target payload names fail generation
instead of silently losing parser coverage. Unknown wire versions dump raw data.

### Generated parsers and NAV helpers

All supported message structs and parser classes, including NAV-PVT and NAV-EOE,
are generated. `ubx_nav.{hpp,cpp}` contains only application-level free functions:

- NAV-PVT and NAV-EOE semantic validation
- NAV-PVT fix-type formatting
- custom NAV-PVT and NAV-EOE debug dumps

Generated parser `valid` means that frame identity, payload length and structural
decoding succeeded. Semantic validity is checked separately by the NAV helpers.

### TCP reader notes

Both transports use `read_ubx_frame()` with byte-reader callbacks. TCP deliberately
uses one-byte `read()` calls, consistent with serial reading, with `SO_RCVTIMEO`
5s and automatic reconnection on disconnect. A timeout warns, discards partial
state, and searches for the next sync point. It does not retain a partial frame.
File/stdin input distinguishes clean EOF from truncated sync/header/payload/checksum;
truncation reports an error and exits nonzero.

### Recording

The latest semantically valid NAV-PVT controls opening/rotation by full UTC
year/month/day. That PVT is written to the newly opened file. NAV-EOE is diagnostic
only: missing or mismatched EOE does not block recording. Invalid PVT does not
change the recording date. Output writes and closing/flushing at EOF or rotation
are checked, with nonzero exit on failure.

### `*_gen.hpp` include order

Generated parser `.cpp` includes: `ubx_{class}_gen.hpp`, `ubx_ids_gen.hpp`,
`string`, `format`, `cstring`.

### Include order

`ubx.hpp` includes: `ubx_def.hpp`, `ubx_names.hpp`, `ubx_nav.hpp`.
`ubx_def.hpp` includes `ubx_ids_gen.hpp`.
`ubx_nav.hpp` includes `ubx_nav_gen.hpp`.

## Testing

Automated schema/name coverage, C++ decoding, and reader smoke tests:

```bash
cd neoubxlogger && make test
```

Manual verification with testdata files (`-n` prevents recording output files):

```bash
cd neoubxlogger && ./neoubxlogger -n -q < ../testdata/20241103T000000.ubx
```
