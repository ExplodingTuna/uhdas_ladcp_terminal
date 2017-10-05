#ifndef CLOCKS_INCLUDED
#define CLOCKS_INCLUDED

#include <time.h>
#include <sys/time.h>

struct clocks {struct timeval realtime, monotonic;};
struct dpclocks {double realtime, monotonic;};

void clocks_read(struct clocks *cptr);
void clocks_diff(struct clocks *cptr, struct timeval *tptr);
void clocks_dp(struct clocks *cptr, struct dpclocks *cdpptr);
void clocks_dday(struct clocks *cptr, struct dpclocks *cdpptr);
double seconds_since(struct clocks *cptr);


#endif


