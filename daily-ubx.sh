#!/usr/bin/env bash
# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Kelei Chen

gpspipe -x 86460 -R | xz -e > /share/ubx24h/"$(date +%Y%m%dT%H%M%S%z)".ubx.xz
