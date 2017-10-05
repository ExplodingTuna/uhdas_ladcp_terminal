
#include <time.h>

#include "clocks.h"

/* https://gist.github.com/jbenet/1087739 */
#ifdef __MACH__
#include <mach/clock.h>
#include <mach/mach.h>

void clocks_read(struct clocks *cp)
{
   clock_serv_t cclock;
   mach_timespec_t treal, tmono;

   host_get_clock_service(mach_host_self(), CALENDAR_CLOCK, &cclock);
   clock_get_time(cclock, &treal);
   mach_port_deallocate(mach_task_self(), cclock);

   host_get_clock_service(mach_host_self(), SYSTEM_CLOCK, &cclock);
   clock_get_time(cclock, &tmono);
   mach_port_deallocate(mach_task_self(), cclock);

   cp->realtime.tv_sec = treal.tv_sec;
   cp->realtime.tv_usec = treal.tv_nsec/1000;
   cp->monotonic.tv_sec = tmono.tv_sec;
   cp->monotonic.tv_usec = tmono.tv_nsec/1000;
}
/* the following could be done more nicely by not using the clocks
   structure, but this is the minimal quick approach for now.
*/
double seconds_since(struct clocks *cptr)
{
   double secs;
   clock_serv_t cclock;
   mach_timespec_t tmono;

   host_get_clock_service(mach_host_self(), SYSTEM_CLOCK, &cclock);
   clock_get_time(cclock, &tmono);
   mach_port_deallocate(mach_task_self(), cclock);

   secs = (tmono.tv_sec - cptr->monotonic.tv_sec);
   secs += ((tmono.tv_nsec/1000.0 - cptr->monotonic.tv_usec) / 1000000.0);
   return secs;
}

#else   /* Linux */
void clocks_read(struct clocks *cp)
{
   struct timespec treal, tmono;
   clock_gettime(CLOCK_REALTIME, &treal);
   clock_gettime(CLOCK_MONOTONIC, &tmono);
   cp->realtime.tv_sec = treal.tv_sec;
   cp->realtime.tv_usec = treal.tv_nsec/1000;
   cp->monotonic.tv_sec = tmono.tv_sec;
   cp->monotonic.tv_usec = tmono.tv_nsec/1000;
}

/* the following could be done more nicely by not using the clocks
   structure, but this is the minimal quick approach for now.
*/
double seconds_since(struct clocks *cptr)
{
   double secs;
   struct timespec tmono;

   clock_gettime(CLOCK_MONOTONIC, &tmono);

   secs = (tmono.tv_sec - cptr->monotonic.tv_sec);
   secs += ((tmono.tv_nsec/1000.0 - cptr->monotonic.tv_usec) / 1000000.0);
   return secs;
}
#endif


void clocks_diff(struct clocks *cptr, struct timeval *tptr)
{
   long udif;
   tptr->tv_sec = cptr->realtime.tv_sec - cptr->monotonic.tv_sec;
   udif = cptr->realtime.tv_usec - cptr->monotonic.tv_usec;
   if (udif < 0)
   {
      udif += 1000000;
      tptr->tv_sec -= 1;
   }
   tptr->tv_usec = udif;
}


void clocks_dp(struct clocks *cptr, struct dpclocks *cdpptr)
{
   cdpptr->realtime = cptr->realtime.tv_sec + cptr->realtime.tv_usec/1000000.0;
   cdpptr->monotonic = cptr->monotonic.tv_sec + cptr->monotonic.tv_usec/1000000.0;
}

void clocks_dday(struct clocks *cptr, struct dpclocks *cdpptr)
{
   cdpptr->realtime = (cptr->realtime.tv_sec +
                           cptr->realtime.tv_usec/1000000.0) / 86400.0;
   cdpptr->monotonic = (cptr->monotonic.tv_sec +
                           cptr->monotonic.tv_usec/1000000.0) / 86400.0;
}


