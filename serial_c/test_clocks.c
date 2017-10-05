/*  Illustration of the realtime versus the monotonic clock. */



#include <stdio.h>
#include <time.h>
#include <sys/select.h>

#include "clocks.h"

int main(int argc, char **argv)
{
   struct timeval timeout, timedif;
   struct clocks times;
   struct dpclocks times_dp, times_dday;
   int i;
   for (i = 0; i < 10; i++)
   {
      timeout.tv_sec = 0;
      timeout.tv_usec = 200000;
      select(1, NULL, NULL, NULL, &timeout);
      clocks_read(&times);
      printf("\nReal:  %10d   %3ld\n", times.realtime.tv_sec,
                                       times.realtime.tv_usec/1000);
      printf("Mono:  %10d   %3ld\n", times.monotonic.tv_sec,
                                       times.monotonic.tv_usec/1000);
      clocks_diff(&times, &timedif);
      printf("Diff:  %10d   %3ld\n", timedif.tv_sec, timedif.tv_usec/1000);
      clocks_dp(&times, &times_dp);
      printf("Seconds: %14.3f  %14.3f\n",
                              times_dp.realtime, times_dp.monotonic);
      clocks_dday(&times, &times_dday);
      printf("Days: %14.8f  %14.8f\n",
                              times_dday.realtime, times_dday.monotonic);

#endif
   }

   return(0);
}
