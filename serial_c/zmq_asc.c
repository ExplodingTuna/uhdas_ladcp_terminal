
/* ----------
   see README.txt
   2012-02-14
   All code here was written by Eric Firing, Univ. Hawaii
   ----------
*/


#include <stdio.h>
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
#include <assert.h>
#include <poll.h>
#include "ser.h"
#include "queue.h"
#include "strmatch.h"
#include "clocks.h"

#include <zmq.h>

void * context;
void * subscriber;

char program_name[] = "zmq_asc";
long initial_time = 0L;
struct queue *q_ptr;
int finished = 0;
FILE *fp_status;
LOGFILE_TYPE *lf_ptr;
int time_tag = 0;

/* On input, buf has two lines: the nmea message line
   and the time tag line.
   On output, the two lines have been swapped in place
   in buf, which is returned, and the nmea message line
   has been copied into the array to which nmea_buf points.
   It's length must be at least 128 characters.
*/

char *swap_lines(char *buf, char *nmea_buf)
{
    static char temp[256];
    static char *timetag;
    int taglength;
    int msglength;

    timetag = strchr(buf, '\n') + 1;
    taglength = strlen(timetag);
    if (taglength < 10 || taglength > 30)
    {
       sermsg("Time tag length is out of range.", 1, 1, 0);
       return NULL;
    }
    strcpy(temp, timetag);
    *timetag = '\0';
    msglength = strlen(buf);
    if (msglength < 6 || msglength > 127)
    {
       sermsg("Message length is out of range.", 1, 1, 0);
       return NULL;
    }

    strcpy(nmea_buf, buf);
    strcat(temp, buf);
    strcpy(buf, temp);
    return buf;
}

int main(int argc, char **argv)
{

   char infilename[256] = "";  /* to replace stdin */
   char outfilename[256] = ""; /* to replace stdout */
   int accept_all = 0;
   struct stringset matchstrings;
   int nstrings;
   int nstep = 1;
   int nn;
   ssize_t nread;
   int ret;
   unsigned int count;
   int result;
   int fd_in = 0; /* stdin */
   int nbufmax = 256 - 1 - sizeof(struct clocks);
   char buf[256];
   char inbuf[2];  /* actually using only one byte */
   char nmea_buf[256];
   int yearbase = 2000;
   int flushblock = 0;
   struct clocks t_rec;
   int first_select = 1;
   int first_serial = 1;

   char zmq_transport[128];  // e.g., "tcp://*:5556"
   int rc;
   zmq_pollitem_t zmq_pollitems[1];
   struct pollfd pollitems[1];

   seteuid(getuid()); /* Drop root privs until needed. */

   fp_status = stdout;

   lf_ptr = make_logfile();

   /* printf("argc= %d\n", argc); */
   while (1)
   {
      ret = getopt(argc, argv, "T:Fy:b:P:i:o:d:f:e:m:M:H:cs:atZ:");
      if (ret == EOF) break; /* End of options */
      switch (ret)
      {
         case 'T':
            initial_time = atol(optarg);
            break;
         case 'F':
            flushblock = 1;
            break;
         case 'y':
            yearbase = atoi(optarg);
            break;
         case 'i':
            strncpy(infilename, optarg, sizeof(infilename)-1);
            break;
         case 'o':
            strncpy(outfilename, optarg, sizeof(outfilename)-1);
            break;
         case 'd':
            strncpy (lf_ptr->fname_path, optarg, sizeof(lf_ptr->fname_path)-2);
            nn = strlen(lf_ptr->fname_path);
            if (lf_ptr->fname_path[nn-1] != '/')
               strcat(lf_ptr->fname_path, "/");
            break;
         case 'f':
            strncpy (lf_ptr->fname_start, optarg, sizeof(lf_ptr->fname_start)-1);
            break;
         case 'e':
            strncpy (lf_ptr->fname_ext, optarg, sizeof(lf_ptr->fname_ext)-1);
            break;
         case 'm':  /* 0: decimal day; 1: seconds; 2: hhmmss; 3: .jyd */
            lf_ptr->fname_method =  atoi(optarg);
            break;
         case 'M':
            lf_ptr->minute_interval = atoi(optarg);
            lf_ptr->hour_interval = 0;
            break;
         case 'H':
            lf_ptr->hour_interval = atoi(optarg);
            lf_ptr->minute_interval = 0;
            break;
         case 's':
            nstep = atoi(optarg);
            break;
         case 'a':
            accept_all = 1;
            break;
         case 't':
            time_tag = 1;
            break;
         case 'Z':
            strncpy(zmq_transport, optarg, 127);
            zmq_transport[127] = '\0';
            break;
         default:
            fprintf (stderr, "Unrecognized command line switch: %c\n", ret);
            exit (EXIT_FAILURE);
      }
   } /* parsing input */
   /* printf("optind = %d\n", optind); */
   nstrings = read_stringset(&matchstrings, argc, argv, optind);
   if (nstrings == -1)
   {
      fprintf (stderr, "ERROR: Too many strings to match.\n");
      exit (EXIT_FAILURE);
   }

   rc = acquire_zmq_lock(zmq_transport);
   if (rc != 0)
   {
      fprintf(stderr, "%s", get_ser_msg());
      exit (EXIT_FAILURE);
   }
   atexit(release_zmq_lock);


   context = zmq_ctx_new();
   subscriber = zmq_socket(context, ZMQ_SUB);
   rc = zmq_connect(subscriber, zmq_transport); // "tcp://localhost:5556");
   assert (rc == 0);

   if (accept_all)
   {
      rc = zmq_setsockopt(subscriber, ZMQ_SUBSCRIBE,
                          "", 0);
      assert (rc == 0);
   }
   else
   {
      int i;
      for (i=0; i<matchstrings.n_strings; i++)
      {
         rc = zmq_setsockopt(subscriber, ZMQ_SUBSCRIBE,
                             matchstrings.string[i],
                             strlen(matchstrings.string[i]));
         assert (rc == 0);
      }
   }

   if (lf_ptr->fname_method == FNAME_JYD)
   {
      lf_ptr->hour_interval = 24;
      lf_ptr->minute_interval = 0;
      strcpy(lf_ptr->mode, "ab");
   }

   set_time_constants(yearbase);

   if (flushblock) { lf_ptr->bufmode = _IOLBF; }

   fp_status = fopen_outfile(outfilename);
   if (fp_status == NULL)
   {
      fprintf(stderr, "%s", get_ser_msg());
      exit (EXIT_FAILURE);
   }
   setup_sermsg(lf_ptr, fp_status);

   fd_in = open_infile(infilename);
   if (fd_in < 0)
   {
      fprintf(stderr, "%s", get_ser_msg());
      exit (EXIT_FAILURE);
   }


   signal(SIGHUP, SIG_IGN);
   signal(SIGINT, SIG_IGN);
   signal(SIGQUIT, SIG_IGN);
   /* signal(SIGTERM, catch_sigterm); */

   result = set_rt(1, 0, 0);  // SCHED_RR
   // Memory is not locked because buffers are allocated dynamically.
   if (result) {fprintf(stderr, "Warning: Real-time optimization "
                 "is not in effect.\n"
                 "As root try 'chmod u+s zmq_asc'\n");}

   set_rt(0, 0, 1);  // drop privileges

   fprintf(stderr, "initial_time: %ld\n", initial_time);
   if (initial_time != 0)
   {
      t_rec.realtime.tv_sec = initial_time;
      t_rec.realtime.tv_usec = 0;
      buf[0] = '\0';
      result = write_line(lf_ptr, buf, strlen(buf), t_rec, 0);
   }

   pollitems[0].fd = fd_in;
   pollitems[0].events = POLLIN;

   zmq_pollitems[0].socket = subscriber;
   zmq_pollitems[0].events = ZMQ_POLLIN;

   sermsg("Starting main loop\n", 0, 0, 1);
   count = 0;
   while (!finished)
   {
      result = poll(pollitems, 1, 0);    // check but don't wait
      if (result == -1)
      {
         perror("poll");
      }
      if (pollitems[0].revents)             // presumably result == 1
      {
         nread = read(fd_in, inbuf, 1);
         if (nread == 1 && inbuf[0] == 'X')
         {
            finished = 1;
            continue;
         }
      }

      result = zmq_poll(zmq_pollitems, 1, 100);  // 0.1 s interval to check
      if (result == -1)
      {
         perror("zmq_poll");
         continue;
      }

      if (first_select)
      {
         sermsg("First return from poll\n", 0, 0, 1);
         first_select = 0;
      }

      if (zmq_pollitems[0].revents)
      {
         nread = zmq_recv(subscriber, buf, nbufmax, 0);
         /* If it is max size, skip it--it must be junk. */
         if (nread == nbufmax || nread == 0)
         {
            if (nread == nbufmax) sermsg("read nbufmax\n", 0, 0, 1);
            if (nread == 0)       sermsg("read 0 bytes\n", 0, 0, 1);
            continue;
         }
         if (nread == -1)
         {
            perror("zmq_recv");
            continue;
         }
         buf[nread] = '\0';
         if (first_serial)
         {
            sermsg("First valid return from zmq read\n", 0, 0, 1);
            first_serial = 0;
         }

         count++;
         if (count >= nstep)
         {
            clocks_read(&t_rec);
            if (swap_lines(buf, nmea_buf) == NULL) continue;
            result = write_line(lf_ptr, buf, strlen(buf), t_rec, 0);
            if (result)
            {
               sermsg(NULL, 1, 0, 1);
            }
            else
            {
               fputs(nmea_buf, fp_status);
            }
            count = 0;
         }
      }
   }

   /* The output file is not explicitly closed, but
      will be closed by the system on exit. */

   sermsg("Exiting normally\n", 0, 0, 1);

   zmq_close(subscriber);
   zmq_ctx_destroy(context);

   return EXIT_SUCCESS;
}
