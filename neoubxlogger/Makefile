CXX	= c++
OPT	= -O2 -pipe -fPIC -fPIE
FLAGS	= $(OPT) -I. -Iinclude -g3 -pedantic -Wall -Wextra
#DBG	= -fsanitize=undefined,integer,nullability -fno-omit-frame-pointer
CXXFLAGS = $(FLAGS) $(DBG) -std=c++11 -MMD -MP
LDFLAGS	= -Wl,-O1 -Wl,--as-needed
OBJS	= neoubxlogger.o ubx.o ubx_names.o ubx_nav.o
GEN_CLASSES = nav rxm mon tim esf hnr log sec cfg ack
GEN_SRCS = $(addprefix ubx_,$(addsuffix _gen.cpp,$(GEN_CLASSES))) ubx_dump_gen.cpp
GEN_HDRS = ubx_ids_gen.hpp ubx_struct_gen.hpp \
           $(addprefix ubx_,$(addsuffix _gen.hpp,$(GEN_CLASSES))) \
           ubx_dump_gen.hpp
GEN_FILES = $(GEN_SRCS) $(GEN_HDRS)
GEN_OBJS = ubx_nav_gen.o ubx_rxm_gen.o ubx_mon_gen.o ubx_tim_gen.o \
           ubx_esf_gen.o ubx_hnr_gen.o ubx_log_gen.o ubx_sec_gen.o \
           ubx_cfg_gen.o ubx_ack_gen.o ubx_dump_gen.o
DEPS	= $(OBJS:.o=.d) $(GEN_OBJS:.o=.d)
PRGS	= neoubxlogger

.PHONY: all clean countline gen regen setup

all: $(PRGS)

GEN_SCRIPT = ../scripts/generate_ubx_parsers.py
GEN_STAMP  = .ubx_codegen.stamp
PYTHON    = .venv/bin/python3
PYUBX2_TYPES = ../3rdparty/pyubx2/src/pyubx2/ubxtypes_core.py \
               ../3rdparty/pyubx2/src/pyubx2/ubxtypes_get.py

setup: .venv
	.venv/bin/pip install pyrtcm pynmeagps

.venv:
	python3 -m venv .venv

gen: $(GEN_STAMP)

regen:
	rm -f $(GEN_STAMP)
	$(MAKE) gen

$(GEN_STAMP): $(GEN_SCRIPT) $(PYUBX2_TYPES) | .venv
	$(PYTHON) $(GEN_SCRIPT)
	touch $@

$(GEN_FILES): | $(GEN_STAMP)
	@test -f $@ || { rm -f $(GEN_STAMP); $(MAKE) $(GEN_STAMP); }

$(OBJS) $(GEN_OBJS): | $(GEN_STAMP)

$(OBJS): ubx_def.hpp

$(GEN_OBJS): %.o: %.cpp
	$(CXX) $(CXXFLAGS) -c -o $@ $<

neoubxlogger: $(OBJS) $(GEN_OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^

clean:
	rm -f $(PRGS) $(OBJS) $(GEN_OBJS) $(DEPS) $(GEN_STAMP) *_gen.cpp *_gen.hpp

countline:
	wc -l *.h *.c

-include $(DEPS)
