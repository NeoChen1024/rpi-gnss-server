#!/usr/bin/env bash
gpspipe -x 86460 -R | xz -e > /share/ubx24h/"$(date +%Y%m%dT%H%M%S%z)".ubx.xz
