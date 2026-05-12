CXX	= c++
OPT	= -O2 -pipe -fPIC -fPIE
FLAGS	= $(OPT) -I. -Iinclude -g3 -pedantic -Wall -Wextra
#DBG	= -fsanitize=undefined,integer,nullability -fno-omit-frame-pointer
CXXFLAGS = $(FLAGS) $(DBG) -std=c++11
LDFLAGS	= -Wl,-O1 -Wl,--as-needed
OBJS	= neoubxlogger.o ubx.o ubx_names.o ubx_nav.o
GEN_OBJS = ubx_nav_gen.o ubx_rxm_gen.o ubx_mon_gen.o ubx_tim_gen.o \
           ubx_esf_gen.o ubx_hnr_gen.o ubx_log_gen.o ubx_sec_gen.o \
           ubx_cfg_gen.o ubx_ack_gen.o ubx_dump_gen.o
PRGS	= neoubxlogger

.PHONY: all clean countline gen setup

all: $(PRGS)

GEN_SCRIPT = ../scripts/generate_ubx_parsers.py
PYTHON    = .venv/bin/python3

setup: .venv
	.venv/bin/pip install pyrtcm pynmeagps

.venv:
	python3 -m venv .venv

gen:
	$(PYTHON) $(GEN_SCRIPT)

# Auto-generate when generated files are missing
$(OBJS) $(GEN_OBJS): ubx_ids_gen.hpp

$(OBJS): ubx_def.hpp

ubx_ids_gen.hpp ubx_struct_gen.hpp:
	$(PYTHON) $(GEN_SCRIPT)

$(GEN_OBJS): %.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

neoubxlogger: $(OBJS) $(GEN_OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^

clean:
	rm -f $(PRGS) $(OBJS) $(GEN_OBJS) *_gen.cpp *_gen.hpp

countline:
	wc -l *.h *.c
