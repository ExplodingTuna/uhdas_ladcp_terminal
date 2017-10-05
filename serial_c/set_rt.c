#ifdef __MACH__
int set_rt(int sched_rr, int lockmem, int drop_priv)
{
    return 0;
}
#else

#include <stdio.h>
#include <sched.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/time.h>
#include <stdlib.h>
#include <time.h>
#include <sys/mman.h>



int set_rt(int sched_rr, int lockmem, int drop_priv)
{
   int retval;
   struct sched_param sp;

   retval = seteuid(0);  /* in case privileges were dropped */
   if (retval)
   {
      perror("In set_rt, seteuid(0)");
      return -1;
   }
   fprintf(stderr, "acquired root privileges\n");

   if (sched_rr)
   {
      sp.sched_priority = sched_get_priority_min(SCHED_RR);
      retval = sched_setscheduler(0, SCHED_RR, &sp);
      if (retval)
      {
         perror("In set_rt, sched_setscheduler");
         return -1;
      }
      fprintf(stderr, "sched_setscheduler successful\n");
   }

   if (lockmem)
   {
      retval = mlockall(MCL_FUTURE);
      if (retval)
      {
         perror("In set_rt, mlockall");
         return -1;
      }
      fprintf(stderr, "mlockall successful\n");
   }

   if (drop_priv)
   {
      /* printf("before: uid %d   euid %d\n", getuid(), geteuid());  */
      retval = seteuid(getuid());
      /* printf("after: uid %d   euid %d\n", getuid(), geteuid());   */

      if (retval)
      {
         perror("In set_rt, seteuid(getuid())");
         return -1;
      }
      fprintf(stderr, "privileges dropped\n");
   }
   return 0;
}

#endif

