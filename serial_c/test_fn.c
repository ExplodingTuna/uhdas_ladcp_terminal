/*
test_fn.c
Derived from ser_asc.c, for use in testing the file opening and naming
system in ser_subs.c.

Every 10 seconds, it writes a line with seconds and microseconds from
the realtime clock, and from the monotonic clock.

For example, make a test file every 5 minutes:
./test_fn -F -d ~/test_fn -f clocks -e jnk -m1 -M5 -t -y 2005

Type "X" to end the test with queue put and get error counts.

2005/03/25
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
#include "ser.h"
#include "queue.h"
#include "strmatch.h"
#include "clocks.h"

char program_name[] = "test_fn";
long initial_time = 0L;
struct queue *q_ptr;
int finished = 0;
FILE *fp_status;
LOGFILE_TYPE *lf_ptr;
int time_tag = 0;



/* The extra "1" in the following routines is the space for
   the nul byte that terminates the string; nread is the number
   of characters not counting the nul.
*/

int pack_line(char *buf, int n, struct clocks t)
{
   memcpy(buf + n + 1, &t, sizeof(t));
   return (n + 1 + sizeof(t));
}

int unpack_line(char *buf, int n, struct clocks *t_ptr)
{
   int ntv = sizeof(struct clocks);
   if (ntv >= n) return 0;
   memcpy(t_ptr, buf + n - ntv, ntv);
   return (n - ntv - 1);
}

void *writer(void *data)
{
   static int N = 256;
   static char buf[256];
   struct clocks tv;
   int n_bytes;
   int n_char;
   int ret;
   int errors = 0;

   while (!finished)
   {
      ret = queue_get(q_ptr, buf, &n_bytes, N);
      if (ret) {errors++;}
      n_char = unpack_line(buf, n_bytes, &tv);
      if (buf[0] == 'X')
      {
         finished = 1;
      }
      else
      {
         ret = write_line(lf_ptr, buf, n_char, tv, time_tag);
         if (ret) sermsg(NULL, 1, 1, 1);
         fputs(buf, fp_status);
      }
   }
   printf("Writer is exiting with %d errors\n", errors);
   return NULL;
}



int main(int argc, char **argv)
{

   char infilename[256] = "";  /* to replace stdin */
   char outfilename[256] = ""; /* to replace stdout */
   char port_name[12] = "ttyS0";
   char speed_string[10] = "4800";
   int accept_all = 0;
   struct stringset matchstrings;
   int nstrings;
   int nstep = 1;
   int nn;
   ssize_t nread;
   int ret;
   int count;
   int result;
   speed_t speed;
   fd_set readfds;
   int fd_com;    /* com port */
   int fd_in = 0; /* stdin */
   char buf[NBUF];
   char inbuf[NBUF];  /* actually using only one byte */
   SERIAL_PORT_TYPE *port_ptr;
   int yearbase = 2000;
   int flushblock = 0;
   struct clocks t_rec;
   int good_msg;
   int npacked;
   int thread_id;
   pthread_t pthread;
   int nbufmax = NBUF - 1 - sizeof(struct timeval);
   int check = 0;  /* check the NMEA checksum? */
   int errors = 0; /* count of queue_put errors */

   struct timeval timeout;

   seteuid(getuid()); /* Drop root privs until needed. */

   fp_status = stdout;

   lf_ptr = make_logfile();

   /* printf("argc= %d\n", argc); */
   while (1)
   {
      ret = getopt(argc, argv, "T:Fy:b:P:i:o:d:f:e:m:M:H:cs:at");
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
         case 'b':
            strncpy(speed_string, optarg, sizeof(speed_string)-1);
            break;
         case 'P':
            strncpy(port_name, optarg, sizeof(port_name)-1);
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
         case 'c':
            check = 1;
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
      fprintf(stderr, get_ser_msg());
      exit (EXIT_FAILURE);
   }
   setup_sermsg(lf_ptr, fp_status);

   fd_in = open_infile(infilename);
   if (fd_in < 0)
   {
      fprintf(stderr, get_ser_msg());
      exit (EXIT_FAILURE);
   }


#if 0
   /* Serial port checking and setup. */
   speed = ser_speed(speed_string);
   if (speed == 0)
   {
      fprintf (stderr, "ERROR: Speed %s is not available\n",
             speed_string);
      exit (EXIT_FAILURE);
   }

   port_ptr = acquire_port(port_name);
   if (port_ptr == NULL)
   {
      fprintf(stderr, get_ser_msg());
      exit (EXIT_FAILURE);
   }

   port_ptr->cur_termios.c_lflag |= ICANON;
   port_ptr->cur_termios.c_iflag |= IGNCR; /* throw away CR; otherwise,
                                   the default is to turn CR into NL */
   port_ptr->cur_termios.c_lflag &= ~(ECHO | ISIG);
   cfsetispeed (&(port_ptr->cur_termios), speed);


   tcsetattr (port_ptr->fd, TCSAFLUSH, &port_ptr->cur_termios);
   atexit(release_port);
   fd_com = port_ptr->fd;
   /* End of serial port setup. */

   signal(SIGHUP, SIG_IGN);
   signal(SIGINT, SIG_IGN);
   signal(SIGQUIT, SIG_IGN);
   /* signal(SIGTERM, catch_sigterm); */

#endif

   q_ptr = queue_create(20, 128);
   result = pthread_create(&pthread, NULL, writer, NULL);
   if (result)
   {
      perror("pthread_create");
   }
   else
   {
      printf("writer thread created\n");
   }
   set_rt(1, 1, 1);    /* This must go *after* pthread_create. */
   /* set_rt(0, 0, 1);   */
   if (initial_time != 0)
   {
      t_rec.realtime.tv_sec = initial_time;
      t_rec.realtime.tv_usec = 0;
      npacked = pack_line(buf, 0, t_rec);
      queue_put(q_ptr, buf, npacked);
   }

   count = 0;
   while (!finished)
   {
      FD_ZERO(&readfds);
      FD_SET (fd_in, &readfds);

      /*FD_SET(fd_com, &readfds);*/
      timeout.tv_sec = 0;            /* <======================= */
      timeout.tv_usec = 10000;
      select( FD_SETSIZE, &readfds, NULL, NULL, &timeout);
      if (FD_ISSET(fd_in, &readfds))
      {
         read(fd_in, inbuf, 1);
         if (inbuf[0] == 'X')
         {
            finished = 1;
            npacked = pack_line(inbuf, 1, t_rec);
            ret = queue_put(q_ptr, buf, npacked);
            if (ret) {errors++;}
         }
      }
      else
      {
         clocks_read(&t_rec);
         sprintf(buf, "%d  %d %d %d\n", t_rec.realtime.tv_sec,
                                        t_rec.realtime.tv_usec,
                                        t_rec.monotonic.tv_sec,
                                        t_rec.monotonic.tv_usec);
         npacked = pack_line(buf, strlen(buf), t_rec);
         queue_put(q_ptr, buf, npacked);
      }
   }

   /* The output file is not explicitly closed, but
      will be closed by the system on exit.  The com port
      is restored by a function registered with atexit */

   /* Give the writer thread time to exit with its message.
      We could also join it...
   */
   sleep(1);
   printf("main thread exiting with %d errors\n", errors);
   return EXIT_SUCCESS;
}
