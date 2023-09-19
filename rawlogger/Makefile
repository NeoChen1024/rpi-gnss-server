CC	= cc
OPT	= -Og -pipe -fPIC -fPIE
FLAGS	= $(OPT) -I. -Iinclude -g3 -pedantic -Wall -Wextra -D_DEFAULT_SOURCE
#DBG	= -fsanitize=undefined,integer,nullability -fno-omit-frame-pointer
CFLAGS = $(FLAGS) $(DBG) -std=c99
LDFLAGS	= -Wl,-O1 -Wl,--as-needed
PRGS	= rawlogger

.PHONY: all clean countline

all: $(PRGS)

countline:
	wc -l *.h *.c

clean:
	rm -f $(PRGS)
