
/* ----------
   see README.txt
   2012-02-14
   All code here was written by Eric Firing, Univ. Hawaii
   ----------

    This is derived from ser_bin.  Differences:

    1) It accepts SIGTERM and SIGINT as equivalent to X via stdin.

    2) It acts as a zmq publisher for the message that is sent after
    each ping is written to disk.

    The modifications are largely transferred from ser_asc_zmq.

    With or without the -Z option, which turns on the publisher
    functionality, this should work as a drop-in replacement for
    ser_bin.
*/


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <time.h>
#include <sys/types.h>
#include <errno.h>
#include <signal.h>
#include <assert.h>
#include <zmq.h>
#include "ser.h"
#include "queue.h"

/*

2006/04/24 EF
    Note: investigate whether exiting the main thread will
    always leave complete records written by the writer thread.
    If not, add a mechanism such as was started in ser_asc,
    in which the writer is signalled to end gracefully, and
    the main thread waits for it.



2004/10/10 EF added the -I "initiate pinging" option, in which
   ser_bin commands an old narrowband, or an Ocean Surveyor,
   to ping.  The OS mode should also work for the Workhorse. The
   -I option uses the -O option to determine whether the block
   type, and therefore the start-pinging command, should be
   NB-style (S207 command with instrument in binary mode), or
   OS/WH-style (CS command, ascii response).

2003/12/11 EF fixed bugs in raw log file ping number and
   adcp dday columns
*/

char program_name[] = "ser_bin_zmq";
struct queue *q_ptr;
long initial_time = 0L;
FILE *fp_status;
int finished = 0;
LOGFILE_TYPE *lf_ptr, *log_ptr = NULL, *binlog_ptr = NULL;
int errlog = 0;

void * context = NULL;
void * publisher = NULL;

static int pipefd[2];

void catch_sigterm(int sig)
{
   write(pipefd[1], "X", 1);
}

int pack_block(unsigned char *buf, int n, struct clocks t, char *logmsg)
{
   int ntv = sizeof(struct clocks);
   int nlog;
   int n_packed;

   nlog = strlen(logmsg) + 1; /* for nul termination */
   memcpy(buf + n, &t, ntv);
   n_packed = n + ntv;
   memcpy(buf + n_packed, logmsg, nlog);
   n_packed += nlog;
   memcpy(buf + n_packed, &n, sizeof(int));
   n_packed = n_packed + sizeof(int);
   return n_packed;
}

int unpack_block(unsigned char *buf, int n_packed,
                  struct clocks *t_ptr,
                  char *logmsg)
{
   int ntv = sizeof(struct clocks);
   int n;
   int nlog;

   memcpy(&n, buf + n_packed - sizeof(int), sizeof(int));
   memcpy(t_ptr, buf + n, ntv);
   nlog = n_packed - n - sizeof(int) - sizeof(struct clocks);
   memcpy(logmsg, buf + n + ntv, nlog);
   /* could use strncpy instead */
   return n;
}

void *writer(void *data)
{
   static int N = 10000;
   static unsigned char buf[10000];
   static char msgbuf[128];
   static char logmsg[60];
   struct clocks tv;
   int n_bytes;
   int n_char;
   int ret;
   int n_get_failed=0;

   while (!finished)
   {
      ret = queue_get(q_ptr, buf, &n_bytes, N);
      if (ret != 0)
      {
         n_get_failed++;
         sermsg_init();
         sermsg_cat("ERROR: queue_get returned %d; count=%d\n",
                                                ret, n_get_failed);
         sermsg(NULL, 0, 0, 1);
         continue; /* QUEUE_ITEM_TOO_BIG */
      }

      n_char = unpack_block(buf, n_bytes, &tv, logmsg);
      if (n_char == 0 && tv.realtime.tv_sec == 0) break;
      /* blank message with 0 realtime signals end */

      ret = write_block(lf_ptr, log_ptr, binlog_ptr, buf, n_char, tv, logmsg);
      if (ret != 0)
      {
         sermsg(NULL, 1, errlog, 1);
         continue;
      }
      snprintf (msgbuf, sizeof(msgbuf), "%s  %ld  %d\n",
            lf_ptr->fname, lf_ptr->offset, n_char);
      sermsg(msgbuf, 1, 0, 0);
      if (publisher != NULL)
      {
         int err;
         /* chop off the newline */
         msgbuf[strlen(msgbuf)-1] = '\0';
         err = zmq_send(publisher, msgbuf, strlen(msgbuf), 0);
         if (err == -1)
         {
            sermsg_init();
            sermsg_cat("ERROR: from zmq_send, %s\n", strerror(errno));
            sermsg(NULL, 1, 0, 1);
         }
      }
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

   int nn;
   ssize_t nread;
   int ret;
   int result;
   static unsigned char buf[NBUF+1];
   static char inbuf[2];  /* actually using only one byte */
   speed_t speed;
   fd_set readfds;
   int fd_com;    /* com port */
   int fd_in = 0; /* stdin */
   SERIAL_PORT_TYPE *port_ptr;


   int n, nc;
   int s_return;
   struct timeval tv_saved;
   double timeout = -1.0;
   int check = 0;
   int block_type = BLOCK_NB;
   struct clocks t_rec;  /* time received */
   int yearbase = 2000;
   int flushblock = 1;
   int c_cc_vmin = 255; /* option v */
   int c_cc_vtime = 255;  /* option V */

   double pingdday;
   int pingnum;
   #if 0
   int last_pingnum = 0;  /* for another disabled option, below */
   #endif
   char logmsg[60] = "";

   pthread_t pthread;
   int npacked;

   int start_pinging = 0;
   int n_put_failed = 0;

   char zmq_transport[128];  // e.g., "tcp://*:5556"
   int rc;

   zmq_transport[0] = '\0';

   seteuid(getuid()); /* Drop root privs until needed. */

   lf_ptr = make_logfile();
   fp_status = stdout;

   while (1)
   {
      ret = getopt(argc, argv,
                  "IT:Fy:b:P:i:o:d:f:e:m:M:H:lOSt:B:rEcv:V:Z:");
      if (ret == EOF) break; /* End of options */
      switch (ret)
      {
         case 'T':
            initial_time = atol(optarg);
            break;
         case 'F':
            /* No effect; for binary acquisition, we have long had
               flushblock set to 1 with no means of changing it.
            */
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
         /* above here, same as ser_asc */
         case 'l':
            log_ptr = make_logfile();
            binlog_ptr = make_logfile();
            break;
         case 'O':
            block_type = BLOCK_OS;  /* Ocean Surveyor or BB, not NarrowBand */
            break;
         case 'I':             /* mnemonic: Initiate */
            start_pinging = 1;
            break;
         case 't':
            timeout = atof(optarg);
            break;
         case 'r':
            /* raw = 1;   */ /* RDI raw (NB, BB, or OS), not DAS ensemble */
            break;
         case 'E':
            errlog = 1;
            break;
         case 'v':
            c_cc_vmin = atoi(optarg);
            break;
         case 'V':
            c_cc_vtime = atoi(optarg);
            break;
         case 'Z':
            strncpy(zmq_transport, optarg, 127);
            zmq_transport[127] = '\0';
            break;
         case '?':
         default:
            fprintf (stderr, "Unrecognized command line switch: %c\n", ret);
            exit (EXIT_FAILURE);
      }
   }

   if (start_pinging)
   {
      start_pinging = block_type;
   }
   if (strlen(zmq_transport))
   {
      context = zmq_ctx_new();
      publisher = zmq_socket(context, ZMQ_PUB);
      rc = zmq_bind(publisher, zmq_transport); // "tcp://*:5556");
      if (rc != 0)
      {
         fprintf (stderr, "Error from zmq_bind: %s\n", strerror(errno));
         exit (EXIT_FAILURE);
      }
   }
   if (lf_ptr->fname_method == FNAME_JYD)
   {
      lf_ptr->hour_interval = 24;
      lf_ptr->minute_interval = 0;
      strcpy(lf_ptr->mode, "ab");
   }

   set_time_constants(yearbase);
   if (flushblock) lf_ptr->flush = 1; /* ensemble */

   if (log_ptr != NULL)
   {
      *log_ptr = *lf_ptr;
      strcat(log_ptr->fname_ext, ".log");
   }
   if (binlog_ptr != NULL)
   {
      *binlog_ptr = *lf_ptr;
      strcat(binlog_ptr->fname_ext, ".log.bin");
   }


   if (timeout > 0.0)
   {
      tv_saved.tv_sec = (int) timeout;
      tv_saved.tv_usec = 1e6 * (timeout - tv_saved.tv_sec);
   }
   else
   {
      tv_saved.tv_sec = 0;
      tv_saved.tv_usec = 100000;  /* microseconds */
   }
   if (c_cc_vmin == 255) c_cc_vmin = 0;
   if (c_cc_vtime == 255) c_cc_vtime = 1;


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

   cfmakeraw (&port_ptr->cur_termios);
   port_ptr->cur_termios.c_cc[VMIN] = c_cc_vmin;
   port_ptr->cur_termios.c_cc[VTIME] = c_cc_vtime; /* tenths of second */
   /* With VMIN 0, the read call will return in VTIME or
   as soon as any characters at all are available.  In practice
   this is at 8 or 16-char intervals.  Efficiency could possibly
   be improved by inserting a sleep(1) in the loop, so that
   fewer reads would be needed.
   */
   cfsetispeed (&(port_ptr->cur_termios), speed);
   tcsetattr (port_ptr->fd, TCSAFLUSH, &port_ptr->cur_termios);

   atexit(release_port);

   fd_com = port_ptr->fd;
   /* End of serial port setup. */

   /* Make the pipe; leave the file descriptors in pipefd. */
   if (pipe(pipefd) == -1)
   {
      fprintf(stderr, "Error: pipe(pipefd) failed\n");
      exit(EXIT_FAILURE);
   }

   signal(SIGHUP, SIG_IGN);
   signal(SIGINT, catch_sigterm);
   signal(SIGQUIT, SIG_IGN);
   signal(SIGTERM, catch_sigterm);

   /* flush_input(fd_com, 1, &port_ptr->cur_termios); */
   /* flush_input stops the program in its tracks if the
      gaps are less than 0.1 second.  I don't think we need
      it any more.
   */

   sermsg("Ready to create queue\n", 0, 0, 1);
   q_ptr = queue_create(50, 128);
   if (q_ptr == NULL)
   {
      fprintf(stderr, "Error: queue_create failed\n");
      exit(EXIT_FAILURE);
   }

   result = pthread_create(&pthread, NULL, writer, NULL);
   if (result) {perror("pthread_create writer"); exit(EXIT_FAILURE);};
   result = set_rt(1, 0, 1);
   // Don't lock the memory; it will block dynamic queue buffer allocation.
   //   use "result = set_rt(1, 1, 1);" only if memory reallocation is
   //   disabled in queue.c
   if (result) {fprintf(stderr, "Warning: Real-time optimization "
                 "is not in effect.\n"
                 "As root try 'chmod u+s ser_bin'\n");}

   if (initial_time != 0)
   {
      t_rec.realtime.tv_sec = initial_time;
      t_rec.realtime.tv_usec = 0;
      npacked = pack_block(buf, 0, t_rec, "");
      queue_put(q_ptr, buf, npacked);
   }

   if (start_pinging == BLOCK_OS)
   {
      if (OS_ping(fd_com) != 0)
      {
         sermsg("ERROR in OS_ping\n", 1, 1, 1);
         sermsg(NULL, 1, 1, 1);
         exit(EXIT_FAILURE);
      }
   }

   if (start_pinging == BLOCK_NB)
   {
      if (NB_ping(fd_com) != 0)
      {
         sermsg("ERROR in NB_ping\n", 1, 1, 1);
         sermsg(NULL, 1, 1, 1);
         exit(EXIT_FAILURE);
      }
   }

   nc = 0;
   while (!finished)
   {
      int ens_started = 0;
      int nb_expected;

      while ( !finished  )
      {
         FD_ZERO(&readfds);
         FD_SET (fd_in, &readfds);
         FD_SET(pipefd[0], &readfds);  /* pipe used by catch_sigterm */
         FD_SET(fd_com, &readfds);
         /* No tv timeout; block until something is readable. */
         s_return = select( FD_SETSIZE, &readfds, NULL, NULL, NULL);
         if (s_return == -1)
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
            }
         }
         if (FD_ISSET(pipefd[0], &readfds))
         {
            nread = read(pipefd[0], inbuf, 1);
            if (nread == 1 && inbuf[0] == 'X')
            {
               finished = 1;
            }
         }
         if (finished)
         {
            int res;

            /* Signal the writer thread to shut down. */
            t_rec.realtime.tv_sec = 0; /* second part of the flag */
            npacked = pack_block(buf, 0, t_rec, "");  /* 0 bytes */
            queue_put(q_ptr, buf, npacked);

            /* Wait for 0.1 seconds of quiet. It doesn't seem like
               this should be necessary, and maybe it isn't.
            */
            res = flush_input(fd_com, 1, &port_ptr->cur_termios, 1.0);
            if (res)
            {
               sermsg("Timeout in initial shutdown flush_input", 1,0,1);
            }
            tcsendbreak(fd_com, 400);
            /* Not sure when tcsendbreak returns; use tcdrain to be
               sure we are waiting until it has finished.
            */
            tcdrain(fd_com);
            /* Now wait for 0.2 seconds of silence before ending
               the program.
            */
            res = flush_input(fd_com, 2, &port_ptr->cur_termios, 2.0);
            if (res)
            {
               sermsg("Timeout in final shutdown flush_input", 1,0,1);
            }
            /* And wait for the writer to end. */
            result = pthread_join(pthread, NULL);
            break;
         }
         else /* must have something on fd_com */
         {
            int ret;

            n = read (fd_com, buf + nc, (sizeof(buf) - nc));
            if (n > 0) nc += n;
            if (n < 0) perror("read");
            if (n == 0)  /* big problem, like unplugged USB serial */
            {
               sermsg("read 0 bytes; quitting\n", 1, 1, 1);
               finished=1;
               continue;
            }

            if (!ens_started)
            {
               ret = shift_to_start(buf, &nc, block_type);
               if (ret > 0)
               {
                  nb_expected = ret + 2; /* add 2 for the checksum */
                  ens_started = 1;
                  clocks_read(&t_rec);  /* near start of transmission, not end */
               }
            }
            if (!(ens_started && nc >= nb_expected))
            {
                continue;
            }

            /* We may have one or more blocks at this point. */
            if (check)
            {
               while (checksum_bad(buf, nb_expected, block_type))
               {
                  sermsg(NULL, 1, errlog, 0);
                  memmove(buf, buf+1, nc-1);
                  nc--;
                  ret = shift_to_start(buf, &nc, block_type);
                  if (ret > 0)
                  {
                     nb_expected = ret + 2; /* add 2 for the checksum */
                     if (nc < nb_expected) break;
                  }
                  else
                  {
                     ens_started = 0;
                     break;
                  }
               }
               if (!(ens_started && nc >= nb_expected))
               {
                   /* Checksum failed and either no new start
                      was found, or, if it was found, there are
                      not enough bytes for a full ensemble; so
                      go back and read more bytes.
                   */
                   continue;
               }

               pingnum = get_pingnum(buf, block_type);
               pingdday = get_pingtime(buf, block_type);
               if (pingdday == -9999.0) sermsg(NULL, 1,1,1);
               snprintf(logmsg, sizeof(logmsg), "%d %.7f", pingnum, pingdday);
            }
            else
            {
               logmsg[0] = '\0';
            }

            /* At this point we should have a block to write out. */
            npacked = pack_block(buf, nb_expected, t_rec, logmsg);
            result = queue_put(q_ptr, buf, npacked);
            if (nb_expected < nc)
            {
               memmove(buf, buf+nb_expected, nc - nb_expected);
               nc -= nb_expected;
               ret = shift_to_start(buf, &nc, block_type);
               if (ret > 0)
               {
                  nb_expected = ret + 2; /* add 2 for the checksum */
               }
               else
               {
                  ens_started = 0;
               }
            }
            else
            {
               nc = 0;
               ens_started = 0;
            }
            if (result)
            {
               n_put_failed++;
               sermsg_init();
               sermsg_cat("ERROR: queue_put returned %d; count=%d; npacked=%d\n",
                                                      result, n_put_failed, npacked);
               sermsg(NULL, 1, 0, 1);
               if (n_put_failed % 100 == 1)
               {
                  queue_print(q_ptr, stderr);
               }
            }

         } /* finished handling fd_com; back to select */
      }  /* end of select loop */
   }  /* end of while loop */

   sermsg("Exiting normally\n", 0, 0, 1);
   fprintf(stderr, "n_put_failed=%d\n", n_put_failed);

   if (publisher != NULL)
   {
      zmq_close(publisher);
      zmq_ctx_destroy(context);
   }
   return EXIT_SUCCESS;
}
