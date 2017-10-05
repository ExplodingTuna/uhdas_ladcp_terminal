CFLAGS=-Wall

LIBS=
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    LIBS += -lrt
endif

all: ser_asc ser_bin ser_asc_zmq zmq_asc ser_bin_zmq

queue.o : queue.h queue.c
ser_subs.o : ser.h queue.h
ser_asc.o : ser.h queue.h ser_asc.c
ser_asc_zmq.o : ser.h queue.h ser_asc_zmq.c zmq_subs.c
zmq_asc.o : ser.h queue.h zmq_asc.c zmq_subs.c
ser_bin.o : ser.h queue.h ser_bin.c
ser_bin_zmq.o : ser.h queue.h ser_bin_zmq.c
strmatch.o: strmatch.h strmatch.c
test_fn.o: ser.h queue.h test_fn.c
clocks.o : clocks.h clocks.c

ser_asc: ser_asc.o ser_subs.o set_rt.o queue.o strmatch.o clocks.o
	gcc -Wall -o ser_asc ser_asc.o ser_subs.o set_rt.o\
		queue.o strmatch.o clocks.o -lpthread $(LIBS)

ser_asc_zmq: ser_asc_zmq.o ser_subs.o zmq_subs.o set_rt.o queue.o strmatch.o clocks.o
	gcc -Wall -o ser_asc_zmq ser_asc_zmq.o zmq_subs.o ser_subs.o set_rt.o\
		queue.o strmatch.o clocks.o -lpthread $(LIBS) -lzmq

zmq_asc: zmq_asc.o zmq_subs.o ser_subs.o set_rt.o queue.o strmatch.o clocks.o
	gcc -Wall -o zmq_asc zmq_asc.o zmq_subs.o ser_subs.o set_rt.o\
		queue.o strmatch.o clocks.o -lpthread $(LIBS) -lzmq

ser_bin: ser_bin.o ser_subs.o set_rt.o queue.o clocks.o
	gcc -Wall -o ser_bin ser_bin.o ser_subs.o set_rt.o\
		queue.o clocks.o -lpthread $(LIBS)

ser_bin_zmq: ser_bin_zmq.o ser_subs.o set_rt.o queue.o clocks.o
	gcc -Wall -o ser_bin_zmq ser_bin_zmq.o ser_subs.o set_rt.o\
		queue.o clocks.o -lpthread $(LIBS) -lzmq


test_fn: test_fn.o ser_subs.o set_rt.o queue.o clocks.o
	gcc -Wall -o test_fn test_fn.o ser_subs.o set_rt.o queue.o strmatch.o\
		clocks.o -lpthread $(LIBS)

test_clocks: test_clocks.o clocks.o
	gcc -Wall -o test_clocks test_clocks.o clocks.o $(LIBS)

clean:
	/bin/rm -f *.o *~

# -p preserves file times
# -s strips the symbol tables
# -T install ser_bin_zmq *as* ser_bin
install:
	install -m 04755  -o root -ps ser_asc /usr/local/bin
	install -m 04755  -o root -ps zmq_asc ser_asc_zmq /usr/local/bin
	install -m 04755  -o root -ps -T ser_bin_zmq /usr/local/bin/ser_bin

