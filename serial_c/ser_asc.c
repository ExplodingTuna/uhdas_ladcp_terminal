
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
#include "ser.h"
#include "queue.h"
#include "strmatch.h"
#include "clocks.h"

char program_name[] = "ser_asc";
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
   int N = 256;
   char buf[256];
   struct clocks times;
   int n_bytes;
   int n_char;
   int ret;
   int started = 0;
   int n_get_failed = 0;

   while (!finished)   /* global flag */
   {
      ret = queue_get(q_ptr, buf, &n_bytes, N);
      /* fprintf(stderr, "returned from queue_get\n"); */
      if (ret)
      {
         /* QUEUE_ITEM_TOO_BIG is the only error return*/
         n_get_failed++;
         sermsg_init();
         sermsg_cat("ERROR: queue_get returned %d; count=%d\n",
                                                ret, n_get_failed);
         sermsg(NULL, 0, 0, 1);
         continue;
      }
      n_char = unpack_line(buf, n_bytes, &times);
      if (n_char == 0 && started) continue; /* second blank line signals end */
      /* fprintf(stderr, "n_char=%d, n_bytes=%d\n", n_char, n_bytes); */
      ret = write_line(lf_ptr, buf, n_char, times, time_tag);
      if (ret) sermsg(NULL, 1, 0, 1);
      fputs(buf, fp_status);
      started = 1;
   }
   fprintf(stderr, "n_char %d, n_get_failed= %d\n", n_char, n_get_failed);
   sermsg("writer ending\n", 0, 0, 1);
   return NULL;
}



int main(int argc, char **argv)
{

   char infilename[256] = "";  /* to replace stdin */
   char outfilename[256] = ""; /* to replace stdout */
   char port_name[NPORTNAME] = "ttyS0";
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
   int nbufmax = 256 - 1 - sizeof(struct clocks);
   char buf[256];
   char inbuf[2];  /* actually using only one byte */
   SERIAL_PORT_TYPE *port_ptr;
   int yearbase = 2000;
   int flushblock = 0;
   struct clocks t_rec;
   int good_msg;
   int npacked;
   int first_select = 1;
   int first_serial = 1;
   pthread_t pthread;
   pthread_attr_t pthread_attr;  /* It IS used, despite gcc warning. */
   int check = 0;  /* check the NMEA checksum? */
   int n_put_failed = 0;

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
      fprintf(stderr, "%s", get_ser_msg());
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

   sermsg("Ready to create queue\n", 0, 0, 1);
   q_ptr = queue_create(50, 128);
   if (q_ptr == NULL)
   {
      fprintf(stderr, "Error: queue_create failed\n");
      exit(EXIT_FAILURE);
   }
   /* Start the writer thread with normal scheduling. */
   /* */
   result = pthread_create(&pthread, NULL, writer, NULL);
   if (result) {perror("pthread_create writer"); exit(EXIT_FAILURE);};
   /* */

   result = set_rt(1, 0, 0);
   // Memory is not locked because buffers are allocated dynamically.
   if (result) {fprintf(stderr, "Warning: Real-time optimization "
                 "is not in effect.\n"
                 "As root try 'chmod u+s ser_asc'\n");}

   /* SCHED_RR is probably not necessary or helpful for the
      writer thread, but it does work. If using it, we might want
      to set the main thread to a higher priority.
   */
   /*
   result = pthread_attr_init(&pthread_attr);
   if (result) {perror("pthread_attr_init");
      exit(EXIT_FAILURE);}
   result = pthread_attr_setinheritsched(&pthread_attr,
                    PTHREAD_INHERIT_SCHED);
   if (result) {perror("pthread_attr_setinheritsched");
      exit(EXIT_FAILURE);}
   result = pthread_create(&pthread, &pthread_attr, writer, NULL);
   if (result) {perror("pthread_create writer"); exit(EXIT_FAILURE);};
   */
   set_rt(0,0,1);

   fprintf(stderr, "initial_time: %ld\n", initial_time);
   if (initial_time != 0)
   {
      t_rec.realtime.tv_sec = initial_time;
      t_rec.realtime.tv_usec = 0;
      buf[0] = '\0';
      npacked = pack_line(buf, 0, t_rec);
      queue_put(q_ptr, buf, npacked);
   }

   sermsg("Starting main loop\n", 0, 0, 1);
   count = 0;
   while (!finished)
   {
      FD_ZERO(&readfds);
      FD_SET (fd_in, &readfds);

      FD_SET(fd_com, &readfds);
      result = select( FD_SETSIZE, &readfds, NULL, NULL, NULL);
      if (first_select)
      {
         sermsg("First return from select\n", 0, 0, 1);
         first_select = 0;
      }
      if (result <= 0)
      {
         perror("select");
         continue;
      }
      if (FD_ISSET(fd_in, &readfds))
      {
         nread = read(fd_in, inbuf, 1);
         if (nread == 1 && inbuf[0] == 'X')
         {
            finished = 1;
            /* Send a blank line to signal the writer; wait
                for it to finish.
            */
            buf[0] = '\0';
            npacked = pack_line(buf, 0, t_rec);
            queue_put(q_ptr, buf, npacked);
            result = pthread_join(pthread, NULL);
            //fprintf(stderr, "pthread_join returned %d\n", result);
            continue;
         }
      }
      if (FD_ISSET(fd_com, &readfds))
      {
         nread = read(fd_com, buf, nbufmax);
         /* If it is max size, skip it--it must be junk. */
         if (nread == nbufmax)
         {
            sermsg("read nbufmax\n", 0, 0, 1);
            continue;
         }
         if (nread == 0)
         {
            sermsg("read 0 bytes; quitting\n", 1, 1, 1);
            finished = 1;
            continue;
         }

         if (nread < 0)
         {
            perror("read");
            continue;
         }
         buf[nread] = '\0';
         if (first_serial)
         {
            sermsg("First valid return from serial read\n", 0, 0, 1);
            first_serial = 0;
         }
         /* fprintf(fp_status, "nread= %d\n", nread); */
         if (accept_all || string_selected(&matchstrings, buf, nstep))
         {
            if (accept_all)
            {
               count++;
            }
            if (!accept_all || count >= nstep)
            {
               clocks_read(&t_rec);
               good_msg = 1;
               if (check)
               {
                  good_msg = GoodNMEA(buf);
               }
               if (good_msg)
               {
                  npacked = pack_line(buf, nread, t_rec);
                  result = queue_put(q_ptr, buf, npacked);
                  if (result)
                  {
                     n_put_failed++;
                     sermsg_init();
                     sermsg_cat("ERROR: queue_put returned %d; count=%d\n",
                                                        result, n_put_failed);
                     sermsg(NULL, 1, 0, 1);
                     if (n_put_failed % 100 == 1)
                     {
                        queue_print(q_ptr, stderr);
                     }
                  }
               }
               else
               {
                  sermsg("ERROR: bad NMEA checksum\n", 1, 0, 0);
               }
               if (accept_all)
               {
                  count = 0;
               }
            }
         }
      }
   }

   /* The output file is not explicitly closed, but
      will be closed by the system on exit.  The com port
      is restored by a function registered with atexit */

   sermsg("Exiting normally\n", 0, 0, 1);
   fprintf(stderr, "n_put_failed=%d\n", n_put_failed);
   return EXIT_SUCCESS;
}
