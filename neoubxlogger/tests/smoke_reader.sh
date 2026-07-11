#!/bin/sh
set -eu

logger=${1:-./neoubxlogger}
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT

# Noise followed by B5 B5 62 must retain the second B5 as the frame sync.
# The two frames are a zero-payload frame and NAV-EOE without NAV-PVT.
printf '\265\265\142\001\002\000\000\003\012\265\142\001\141\004\000\000\000\000\000\146\307' |
	"$logger" -n -q 2>"$tmp"

if grep -q 'Invalid frame' "$tmp"; then
	cat "$tmp" >&2
	exit 1
fi
grep -q 'WASTED 1 Bytes' "$tmp"
grep -q 'Ignoring NAV-EOE without a valid NAV-PVT' "$tmp"

printf '\265\142\001\141\004\000\000\000\000\000\146\307' |
	"$logger" -n -d 2>"$tmp"
grep -q '(NAV-EOE, iTOW=0)' "$tmp"

# Exercise a fully generated std::format-based dump.
printf '\265\142\005\001\002\000\001\002\013\057' |
	"$logger" -n -d 2>"$tmp"
grep -q '(ACK-ACK, clsID=1, msgID=2)' "$tmp"
