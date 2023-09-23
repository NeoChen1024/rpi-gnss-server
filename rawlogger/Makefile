CXX	= c++
OPT	= -O2 -pipe -fPIC -fPIE
FLAGS	= $(OPT) -I. -Iinclude -g3 -pedantic -Wall -Wextra
#DBG	= -fsanitize=undefined,integer,nullability -fno-omit-frame-pointer
CXXFLAGS = $(FLAGS) $(DBG) -std=c++11
LDFLAGS	= -Wl,-O1 -Wl,--as-needed
OBJS	= rawlogger.o ubx.o ubx_names.o ubx_nav.o
PRGS	= rawlogger

.PHONY: all clean countline

all: $(PRGS)

rawlogger: $(OBJS)
	$(CXX) $(LDFLAGS) -o $@ $^

countline:
	wc -l *.h *.c

clean:
	rm -f $(PRGS) $(OBJS)
