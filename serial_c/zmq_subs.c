#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <time.h>



#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <signal.h>


#include <zmq.h>

#include "ser.h"
#include "clocks.h"


extern time_t t_epoch;

extern char program_name[];
static char lockfile[128];
static const char lockprefix[] = "/var/lock/LCK..";

int acquire_zmq_lock(char *transport_name)
{
   pid_t pid = 0;
   FILE *fp;
   int nr;
   int k;
   char *chrptr;

   sermsg_init();

   if (strlen(lockprefix) + strlen(transport_name) > 127)
   {
      sermsg_cat("ERROR: transport name %s is too long.\n", transport_name);
      return -1;
   }

   strcpy(lockfile, lockprefix);
   chrptr = lockfile + strlen(lockfile);
   for (k=0; k<strlen(transport_name); k++)
   {
      // Replace slash with dash.
      if (transport_name[k] == '/')
      {
         *chrptr = '-';
      }
      else
      {
         *chrptr = transport_name[k];
      }
      chrptr++;
   }

   fp = fopen(lockfile, "r");
   if (fp)
   {
      nr = fscanf(fp, "%d", &pid);
      fclose(fp);
      /* fprintf(stderr, "PID: %d\n", pid); */
      if (nr == 1)
      {
         sermsg_cat("Pid from lock file: %d\n", pid);
         if (kill(pid, 0) == 0)
         {
            sermsg_cat("Pid is in process table.\n");
            /* process exists */
            k = kill(pid, SIGTERM);
            sermsg_cat("SIGTERM returned %d\n", k);
            k = kill(pid, SIGKILL);
            sermsg_cat("SIGKILL returned %d\n", k);
         }
      }
   }
   fp = fopen(lockfile, "w");
   if (fp == NULL)
   {
      sermsg_cat("ERROR: Can't open lockfile %s.\n", lockfile);
      return(-1);
   }
   if (fprintf(fp, "%d %s %d\n", getpid(), program_name, getuid()) < 1)
   {
      sermsg_cat("ERROR: Can't write to lock file %s.\n", lockfile);
      return(-1);
   }
   fclose(fp);
   chmod(lockfile, S_IREAD | S_IWRITE | S_IRGRP | S_IWGRP | S_IROTH);

   return(0);
}


void release_zmq_lock(void)
{
   if (unlink(lockfile))
   {
      fprintf(stderr, "Can't remove lock file %s.\n", lockfile);
   }
}



// quick modification of write_line
int zmq_broadcast(void *publisher, char *buf, int nb, struct clocks t,
                  int time_tag)
{
   struct dpclocks t_dday;
   static char outbuf[256]; // Q&D
   static char timetag[64];  // more than big enough
   int err;

   if (nb == 0)
   {
      return 0;
   }
   // temporary:
   if (nb > 100)
   {
      printf("message is too long: nb = %d\n", nb);
      return -2;
   }
   outbuf[0] = '\0';
   if (time_tag)
   {
      clocks_dday(&t, &t_dday);
      sprintf(timetag, "$UNIXD,%.7f,%.7f\n",
                     (difftime(t.realtime.tv_sec, t_epoch) +
                     t.realtime.tv_usec * 1e-6) / 86400.0,
                     t_dday.monotonic);
   }
   strcpy(outbuf, buf);
   strcat(outbuf, timetag);
   err = zmq_send(publisher, outbuf, strlen(outbuf), 0);

   if (err == -1)
   {
      return -1;
   }
   return 0;
}

