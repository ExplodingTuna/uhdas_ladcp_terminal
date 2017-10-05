/*

   ser_subs.c

   Serial port support routines, presently designed for simple
   serial port programs, handling only a single port at a time.

*/



#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include <time.h>
/* #include <sys/time.h> */
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <signal.h>
#include "ser.h"
#include "clocks.h"

/* We are almost certainly on little-endian hardware; we are
   not supporting older Mac hardware.  On the off chance that
   we might be running on a Linux big-endian system, however,
   we will go ahead and check the endianness if not on OSX.
*/
#ifndef __MACH__
#   include <endian.h>
#   if __BYTE_ORDER == __LITTLE_ENDIAN
#       define byte_order_line "little\n"
#   else
#       define byte_order_line "big\n"
#   endif
#else
#   define byte_order_line "little\n"
#endif

extern char program_name[];

static SERIAL_PORT_TYPE port;
static  struct termios stdin_termio, init_stdin;

/*--------------------------------------------------------------*/
/* Messages, both routine and error, are handled by this section */

static char ser_msg[512];      /* A buffer for accreting a message. */
static FILE *fp_status;        /* A file (or pipe) for general communication. */
static LOGFILE_TYPE *err_log;  /* Error log file to go with a given
                                                data file.  */

/* Give routines access to the message buffer. */
char *get_ser_msg(void)
{
   return(ser_msg);
}

/* Two setup operations:
     1) Clone the input lf_ptr, append ".err", and make it
        the local err_log.
     2) Connect an existing stream (input file pointer)
        to the communication file pointer, fp_status.
*/
int setup_sermsg(LOGFILE_TYPE *lf_ptr, FILE *fp)
{
   fp_status = fp;
   err_log = make_logfile();
   *err_log = *lf_ptr;
   err_log->bufmode = _IOLBF;
   strcat(err_log->fname_ext, ".err");
   return(0);   /* Error checking may need to be added. */
}


/* Write a message to any or all of three destinations.
   If the first argument, msg, is a null pointer, the message
   is taken from the local buffer, ser_msg.  A time stamp is
   prepended to the message.  Arguments 2-4 are TRUE/FALSE flags
   controlling output to the communication stream, the error log
   file, and standard error.
*/
void sermsg(char *msg, int to_status, int to_errlog, int to_stderr)
{
   char errbuf[300];
   struct   tm t_tm;
   struct timeval tv;
   time_t   t_secs;
   FILE *fp_err;

   if (msg == NULL) msg = ser_msg;
   t_secs = time(NULL);
   tv.tv_sec = t_secs;
   tv.tv_usec = 0;
   gmtime_r (&t_secs, &t_tm);

   snprintf(errbuf, sizeof(errbuf), "%d %02d:%02d:%02d %s", t_tm.tm_yday+1,
         t_tm.tm_hour, t_tm.tm_min, t_tm.tm_sec,  msg);
   if (to_status) fputs(errbuf, fp_status);
   if (to_errlog)
   {
      fp_err = get_fp(err_log, tv);
      fputs(errbuf, fp_err);
   }
   if (to_stderr) fputs(errbuf, stderr);
}

void sermsg_cat(char *fmt, ...)
{
   int n;
   n = strlen(ser_msg);
   va_list args;
   va_start(args, fmt);
   vsnprintf(ser_msg + n, sizeof(ser_msg) - n, fmt, args);
   va_end(args);
}

void sermsg_init(void)
{
   ser_msg[0] = '\0';
}

/*----------end sermsg functions-----------------------------------*/

/*----------------------------------------------------------------*/
/* Serial port methods and functions */

SERIAL_PORT_TYPE *acquire_port(char *port_name)
{
   pid_t pid = 0;
   FILE *fp;
   int nr;
   int k;
   int result;

   sermsg_init();

   strncpy(port.name, port_name, sizeof(port.name)-1);
   snprintf(port.devname, sizeof(port.devname), "/dev/%s", port.name);
   snprintf(port.lockfile, sizeof(port.lockfile), "/var/lock/LCK..%s", port.name);

   fp = fopen(port.lockfile, "r");
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
   fp = fopen(port.lockfile, "w");
   if (fp == NULL)
   {
      sermsg_cat("ERROR: Can't open lockfile %s.\n", port.lockfile);
      return(NULL);
   }
   if (fprintf(fp, "%d %s %d\n", getpid(), program_name, getuid()) < 1)
   {
      sermsg_cat("ERROR: Can't write to lock file %s.\n", port.lockfile);
      return(NULL);
   }
   fclose(fp);
   chmod(port.lockfile, S_IREAD | S_IWRITE | S_IRGRP | S_IWGRP | S_IROTH);

   port.fd = open(port.devname, O_RDWR);
   if (port.fd < 0)
   {
      sermsg_cat("ERROR: Can't open serial port: %s.\n", port.devname);
      unlink(port.lockfile);
      return(NULL);
   }

   result = tcgetattr(port.fd, &port.def_termios);
   if (result)
   {
      sermsg_cat(
            "ERROR: Can't get attributes for serial port: %s.\n", port.devname);
      unlink(port.lockfile);
      close(port.fd);
      return(NULL);
   }
   port.cur_termios = port.def_termios;

   return(&port);
}


void release_port(void)
{
   if (unlink(port.lockfile))
   {
      fprintf(stderr, "Can't remove lock file %s.\n", port.lockfile);
   }
   tcsetattr (port.fd, TCSAFLUSH, &port.def_termios);
   close(port.fd);
}

int ser_speed(char *speed_string)
{
   int speed, speed_num;

   speed_num = atoi(speed_string);
   switch (speed_num)
   {
      case (2400):   speed = B2400; break;
      case (4800):   speed = B4800; break;
      case (9600):   speed = B9600; break;
      case (19200):  speed = B19200; break;
      case (38400):  speed = B38400; break;
      case (57600):  speed = B57600; break;
      case (115200): speed = B115200; break;
      default:       speed = 0;
   }
   return(speed);

}

/*
    timeout is in seconds.
    If flushing isn't finished after this interval,
    then 1 is returned; otherwise return 0.
*/

int flush_input (int fd, int tenths, struct termios *t_ptr, double timeout)
{
   char junk[100];
   int nc;
   int vmin, vtime;
   struct clocks clocks_start;
   double diffsecs;
   int ret = 0;

   vmin = t_ptr->c_cc[VMIN];
   vtime = t_ptr->c_cc[VTIME];

   t_ptr->c_cc[VMIN] = 0;
   t_ptr->c_cc[VTIME] = tenths; /* tenths of second */

   tcsetattr (fd, TCSAFLUSH, t_ptr);

   clocks_read(&clocks_start);
   nc = 1;
   while ( nc != 0)
   {
      nc = read(fd, junk, 100);
      diffsecs = seconds_since(&clocks_start);
      if (diffsecs >= timeout)
      {
         ret = 1;
         break;
      }

   }
   t_ptr->c_cc[VMIN] = vmin;
   t_ptr->c_cc[VTIME] = vtime;
   tcsetattr (fd, TCSAFLUSH, t_ptr);
   return ret;
}

int OS_ping(int fd)
{
   int n, i, j, icmd = 0;
   int ret = 1;
   char initcmd[] = "CS\r\n";
   char buf[1];
   char received[20];
   struct termios term_save, term_new;

   tcgetattr(fd, &term_save);
   term_new = term_save;
   term_new.c_cc[VMIN] = 0;
   term_new.c_cc[VTIME] = 1;
   tcsetattr(fd, TCSAFLUSH, &term_new);


   sermsg_init();
   n = write(fd, initcmd, 3);   /* We don't send the LF. */
   if (n != 3)
   {
      sermsg_cat("Write failed in OS_ping: n = %d\n", n);
      return 1;
   }
   for (i = 0, j=0; i < 20; i++)
   {
      n = read(fd, buf, 1);
      if (n == 1)
      {
         if (buf[0] == initcmd[icmd]) icmd++;
         received[j] = buf[0];
         j++;
      }
      if (icmd == 4)
      {
         ret = 0;   /* success */
         break;
      }
   }
   tcsetattr(fd, TCSAFLUSH, &term_save);
   received[j] = '\0';
   if (ret != 0)
   {
      sermsg_cat("Response in OS_ping: <%s>\n", received);
   }
   return ret;
}

int NB_ping(int fd)
{
   int n, i;
   int nbuf;
   int ret = 1;
   char initcmd[] = "S207"; /*   should be good for default */
   /* char initcmd[] = "S239";*/ /* was necessary on the Gould */
   unsigned char cmdbuf[20];
   unsigned short int cs = 0;
   char buf[1];
   struct termios term_save, term_new;
   struct timespec delay1, delay2;
   int error = 0;

   sermsg_init();
   delay1.tv_sec = 0;
   delay1.tv_nsec = 1000000 * 50; /* 50 milliseconds */

   tcgetattr(fd, &term_save);
   term_new = term_save;
   term_new.c_cc[VMIN] = 0;
   term_new.c_cc[VTIME] = 1;
   tcsetattr(fd, TCSAFLUSH, &term_new);

   for (i = 0; i < strlen(initcmd); i++)
   {
      cmdbuf[i] = initcmd[i];
      cs += cmdbuf[i];
   }
   /* append the checksum */
   cmdbuf[i] = (unsigned char) (cs >> 8);    /* MSB first */
   i++;
   cmdbuf[i] = (unsigned char) (cs & 0xff);  /* LSB */
   i++;
   nbuf = i;
   /* Send the command with checksum. Delay between characters. */
   for (i = 0; i < nbuf; i++)
   {
      write(fd, cmdbuf + i, 1);
      nanosleep(&delay1, &delay2);
   }
   /* Timout in the read operations is the 0.1 second set by VTIME */
   buf[0] = 0;
   /* Read the first byte. */
   for (i = 0; i < 10; i++)
   {
      n = read(fd, buf, 1);
      if (n == 1) break;
   }
   if (buf[0] == 0x15)    /* If NAK, read the error code. */
   {
      for (i = 0; i < 5; i++)
      {
         n = read(fd, buf, 1);
         if (n == 1) break;
      }
      error = buf[0];
      sermsg_cat( "Error code in NB_ping: %d\n", error);
      ret = 1;
   }
   else if (buf[0] != 6)
   {
      sermsg_cat("Error: unrecognized reply in NB_ping: %d\n", buf[0]);
      ret = 1;
   }
   else
   {
      ret = 0;
   }
   tcsetattr(fd, TCSAFLUSH, &term_save);
   return ret;
}




/*------------------end serial port functions--------------------*/


/*-----------------------------------------------------------------*/

time_t t_epoch;
struct tm tm_epoch;
void set_time_constants(int year)
{
   tm_epoch.tm_sec = 0;
   tm_epoch.tm_min = 0;
   tm_epoch.tm_hour = 0;
   tm_epoch.tm_mday = 1;
   tm_epoch.tm_mon = 0;
   tm_epoch.tm_year = year - 1900;
   putenv("TZ=UTC");

   t_epoch = mktime(&tm_epoch);
}

/* methods for LOGFILE_TYPE */

LOGFILE_TYPE *make_logfile(void)
{
   LOGFILE_TYPE *lf;

   lf = calloc(1, sizeof(LOGFILE_TYPE));
   if (lf != NULL)
   {
      lf->time_to_open = 0;
      lf->fp = NULL;
      lf->fname_method = FNAME_DD;
      lf->minute_interval = 0;
      lf->hour_interval = 2;
      lf->flush = 0;
      lf->bufmode = _IOFBF;
      strcpy(lf->mode, "wb");
   }
   return(lf);
}

void destroy_logfile(LOGFILE_TYPE *lf_ptr)
{
   if (lf_ptr->fp != NULL)  fclose(lf_ptr->fp);
   free(lf_ptr);
}

/* Return an existing open file pointer, or make a new
   one if necessary, based on the input time. If the
   new filename corresponds to an existing file, return
   NULL instead of opening (and clobbering) it.
*/
FILE *get_fp(LOGFILE_TYPE *lf_ptr, struct timeval t)
{
   struct tm tm_fn;  /* Time used for new FileName */
   struct stat stat_buf;
   time_t t_filename /*, t_tto*/;
   int seconds, ret;
   char buf[512];

   sermsg_init();

   /*fprintf(stderr, "starting t.tv_sec %d\n", t.tv_sec);*/
   if (t.tv_sec == 0)
   {
      ret = gettimeofday(&t, NULL);
      if (ret)
      {
         sermsg_cat( "ERROR in gettimeofday, %d, %s", errno, strerror(errno));
         return NULL;
      }
   }
   lf_ptr->time = t.tv_sec;
   lf_ptr->time_usec = t.tv_usec;

   /*fprintf(stderr, "t.tv_sec %d,  tto %d\n", t.tv_sec, lf_ptr->time_to_open);*/
   if (t.tv_sec >= lf_ptr->time_to_open)
   {
      /* file opening interval in seconds */
      seconds= lf_ptr->minute_interval * 60 +
                           lf_ptr->hour_interval * 3600;
      if (lf_ptr->fp == NULL || lf_ptr->time_to_open == 0)
      {
         /* No file is open, or a new file is forced by using
         time_to_open = 0 as a flag: name the file based on
         the time passed into this function, or on time
         from gettimeofday call above.
         */
         t_filename = t.tv_sec;
      }
      else
      {
         /* Routine change of file based on specified time
         boundaries; name the file based on the nominal time,
         not the time passed in.
         We are using a quick method to find the nearest boundary
         prior to the present time; it will work if there are no
         intervening leap-seconds.  It seems that standard C
         functions ignore leap-seconds anyway.
         */
         t_filename = (t.tv_sec / seconds) * seconds ;
      }
      lf_ptr->time_opened = t_filename;
      lf_ptr->time_to_open = ((t_filename / seconds) + 1) * seconds;
      /*printf("t_filename %d  time_to_open %d\n",
               t_filename, lf_ptr->time_to_open);*/
      gmtime_r(&t_filename, &tm_fn);
      /* Make new filename. */
      switch(lf_ptr->fname_method)
      {
         case FNAME_DD:
            snprintf(lf_ptr->fname, sizeof(lf_ptr->fname),
                    "%s%04d_%03d_%05.0f.%s",
                    lf_ptr->fname_start,
                    tm_fn.tm_year + 1900,
                    tm_fn.tm_yday,
                    (1e5 / 86400) * (tm_fn.tm_sec + 60 * tm_fn.tm_min
                                        + 3600 * tm_fn.tm_hour),
                    lf_ptr->fname_ext);
            break;
         case FNAME_HHMMSS:
            snprintf(lf_ptr->fname, sizeof(lf_ptr->fname),
                    "%s%04d_%03d_%02d%02d%02d.%s",
                    lf_ptr->fname_start,
                    tm_fn.tm_year + 1900,
                    tm_fn.tm_yday,
                    tm_fn.tm_hour,
                    tm_fn.tm_min,
                    tm_fn.tm_sec,
                    lf_ptr->fname_ext);
            break;
         case FNAME_SEC:
            snprintf(lf_ptr->fname, sizeof(lf_ptr->fname),
                    "%s%04d_%03d_%05d.%s",
                    lf_ptr->fname_start,
                    tm_fn.tm_year + 1900,
                    tm_fn.tm_yday,
                    (tm_fn.tm_sec + 60 * tm_fn.tm_min
                                        + 3600 * tm_fn.tm_hour),
                    lf_ptr->fname_ext);
            break;
         case FNAME_JYD:
            snprintf(lf_ptr->fname, sizeof(lf_ptr->fname),
                    "%s%04d.%03d%s",
                    lf_ptr->fname_start,
                    tm_fn.tm_year + 1900,
                    tm_fn.tm_yday,
                    lf_ptr->fname_ext);
            break;
            /* Note: for FNAME_JYD, the lf_ptr->mode must
               be set to "a" or "ab".
            */
      }
      strncpy(buf, lf_ptr->fname_path, sizeof(buf));
      strncat(buf, lf_ptr->fname, sizeof(buf) - strlen(buf) - 1);
      /* printf(">>%s<<\n", buf);   */
      /* Close previous file, if any. */
      if (lf_ptr->fp != NULL) {fclose(lf_ptr->fp);}
      /* If the new filename corresponds to an existing file,
         it is an error--unless we will append to the file. Instead of
         checking the fname_method, we could directly check lf_ptr->mode.
      */
      if ((lf_ptr->fname_method != FNAME_JYD) && stat(buf, &stat_buf) == 0)
      {
         sermsg_cat( "ERROR in get_fp: file %s already exists.\n", buf);
         return NULL;
      }
      lf_ptr->fp = fopen(buf, lf_ptr->mode);
      if (lf_ptr->fp == NULL)
      {
         sermsg_cat( "ERROR in get_fp: failure to open file %s.\n", buf);
         return NULL;
      }
      ret = chmod(buf, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
      if (ret == -1)
      {
         sermsg_cat("ERROR in get_fp: failure to chmod file %s.\n", buf);
         return NULL;
      }
      setvbuf(lf_ptr->fp, NULL, lf_ptr->bufmode, 0);
   }

   return(lf_ptr->fp);
}

/* Write an ascii line, optionally preceded by a pseudo-NMEA
   time tag string.
   Return -1 if attempt to open file fails, 1 if there is
   an error writing to the file, and 0 if it is successful.
   If the number of bytes to write is zero, just open the file
   and return 0.
*/
int write_line(LOGFILE_TYPE *lf_ptr, char *buf, int nb,
               struct clocks t, int time_tag)
{
   struct dpclocks t_dday;
   FILE *fp;

   sermsg_init();
   fp = get_fp(lf_ptr, t.realtime);
   if (fp == NULL)
   {
      sermsg_cat("ERROR in write_line: can't open file\n");
      return -1;
   }
   if (nb == 0)
   {
      return 0;
   }
   if (time_tag)
   {
      clocks_dday(&t, &t_dday);
      fprintf(fp, "$UNIXD,%.7f,%.7f\n",
                     (difftime(lf_ptr->time, t_epoch) +
                     lf_ptr->time_usec * 1e-6) / 86400.0,
                     t_dday.monotonic);
   }
   if ( fwrite(buf, 1, nb, fp) != nb)
   {
      sermsg_cat( "ERROR in write_line, %d, %s", errno, strerror(errno));
      return 1;
   }
   /* printf ("file closed\n"); */
   return 0;

}


void write_binlog_header(FILE *fp)
{
   fprintf(fp, "%d %d %s\n", 6, 8, "ser_bin_log");
   fprintf(fp, "unix_dday\noffset\nn_bytes\npingnum\ninstrument_dday\nmonotonic_dday\n");
   fprintf(fp, byte_order_line);
   fflush(fp);
}


/* Write a binary block.
   Return -1 if attempt to open file fails, 1 if there is
   an error writing to the file, and 0 if it is successful.
   If the number of bytes to write is zero, just open the file
   and return 0.
*/

int write_block(LOGFILE_TYPE *ens_ptr,
                LOGFILE_TYPE *log_ptr,
                LOGFILE_TYPE *binlog_ptr,
                unsigned char *buf, int nb,
                struct clocks t_secs,
                char *logmsg)
{
   struct dpclocks t_dday;
   FILE *fp, *fplog, *fpbinlog;
   double pc_dday;

   sermsg_init();
   /* Open all three files right away, so that an empty block
      will cause them to be opened with identical names based
      on the initial time.
   */
   fp = get_fp(ens_ptr, t_secs.realtime);
   if (fp == NULL)
   {
      return -1;
   }
   if (log_ptr != NULL)
   {
      fplog = get_fp(log_ptr, t_secs.realtime);
      if (fplog == NULL)
      {
         return -1;
      }
   }
   if (binlog_ptr != NULL)
   {
      fpbinlog = get_fp(binlog_ptr, t_secs.realtime);
      if (fpbinlog == NULL)
      {
         return -1;
      }
      if (ftell(fpbinlog) == 0)
      {
         write_binlog_header(fpbinlog);
      }
   }
   if (nb == 0)  /* It is an empty block; all we need is the open files. */
   {
      return 0;
   }
   ens_ptr->offset = ftell(fp);
   if ( fwrite(buf, 1, nb, fp) != nb)
   {
      sermsg_cat( "ERROR in write_block, %d, %s\n", errno, strerror(errno));
      return 1;
   }
   if (ens_ptr->flush) fflush(fp);
   clocks_dday(&t_secs, &t_dday);
   pc_dday = (difftime(t_secs.realtime.tv_sec, t_epoch) +
                     t_secs.realtime.tv_usec * 1e-6) / 86400.0;
   if (log_ptr != NULL)
   {
      fprintf(fplog, "%.7f %ld %d %s %.7f\n",
                      pc_dday, ens_ptr->offset, nb, logmsg, t_dday.monotonic);
      if (log_ptr->flush) fflush(fplog);
   }
   if (binlog_ptr != NULL)
   {
      double record[6] = {0.0, 0.0, 0.0, -1.0, 1e38, 0.0};
      record[0] = pc_dday;
      record[1] = (double) ens_ptr->offset;
      record[2] = (double) nb;
      sscanf(logmsg, "%lf %lf", &(record[3]), &(record[4]));  /* pingnum, pingdday */
      record[5] = t_dday.monotonic;
      fwrite(record, sizeof(double), 6, fpbinlog);
      if (binlog_ptr->flush) fflush(fpbinlog);
   }

   return 0;
}


/*----------------end logfile object methods----------------------*/

FILE *fopen_outfile(char *outfilename)
{
   int fd_status;
   FILE *fp_status;

   sermsg_init();
   if (outfilename[0] != '\0')
   {
      fd_status = open(outfilename, O_RDWR | O_NONBLOCK | O_APPEND);
      /* If it is a pipe, and there is not yet a listener,
         it has to be opened read-write for the open to complete.
         Nonblock is chosen so that writes will not hang if the
         listener goes away.
      */
      if (fd_status < 0) {
         perror("open_outfile");
         sermsg_cat("Unable to open output file >>%s<<\n", outfilename);
         return(NULL);
      }
      fp_status = fdopen(fd_status, "a+");
      if (fp_status == NULL)  {
         perror("open_outfile");
         sermsg_cat( "Unable to open output file >>%s<<\n", outfilename);
         return(NULL);
      }
      setvbuf(fp_status, NULL, _IOLBF, 0);
      /* From now on, errors go to fp_status, which may not be stdout. */
      return(fp_status);
   }
   else
   {
      return(stdout);
   }
}

int open_infile(char *infilename)
{
   int fd_in;

   sermsg_init();
   if (infilename[0] != '\0')
   {
      /* Open command input file, if not stdin. */
      fd_in = open(infilename, O_RDWR);
      if (fd_in < 0) {
         perror("open_infile");
         sermsg_cat( "ERROR: Unable to open input file >>%s<<\n",
                     infilename);
         return(-1);
      }
   }
   else
   {
      fd_in = 0;
   }
   /* Command input setup */
   tcgetattr(fd_in, &init_stdin);
   stdin_termio = init_stdin;
   stdin_termio.c_cc[VMIN] = 0;
   stdin_termio.c_cc[VTIME] = 0;
   stdin_termio.c_lflag  &= ~ICANON;
   tcsetattr(fd_in, TCSANOW, &stdin_termio);
   return(fd_in);
}


int block_size(unsigned char *buf, int nc, int block_type)
{
   int nb;

   if (nc < 4) return 0;  /* Not big enough to test. */
   if (block_type == BLOCK_NB)
   {
      if ((buf[2] * 256 + buf[3]) != 63) return -1;  /* leader is 63 bytes */
      nb = (buf[0] * 256 + buf[1]);
      if (nb > 67 && nb < NBUF) return nb;
      else return -nb;  /* flag: unreasonable number of bytes */
   }
   /*  (block_type == BLOCK_OS) */
   if ((buf[0] != 0x7f) || (buf[1] != 0x7f)) return -1; /* flag values */
   nb = (buf[3] * 256 + buf[2]);
   if (nb > 117 && nb < NBUF) return nb;
   else return -nb;
}

int shift_to_start(unsigned char *buf, int *nc_ptr, int block_type)
{
   int i;
   int ret;
   int nc = *nc_ptr;

   for (i=0; i<nc; i++)
   {  // fprintf(stderr, "%d ", buf[i]);
      ret = block_size(buf+i, nc-i, block_type);
      // if (buf[i+2] == 0) fprintf(stderr, ">%d %d %d<\n", buf[i+3], buf[i], buf[i+1]);
      if (ret >= 0) break;
   }
   *nc_ptr = nc - i;
   if (*nc_ptr > 0)
   {
      memmove(buf, buf+i, *nc_ptr);
   }
   //fprintf(stderr, "shift_to_start: %d  %d  %d\n", nc, *nc_ptr, ret);
   return ret;
   /* Return value is block size if the start of a block was
      found; otherwise it is 0.  It should never be negative,
      because if we can't find the start of a block, we should
      always run out of bytes to test.

      Upon return, the contents of buf have been shifted left
      to eliminate all rejected bytes, and *nc_ptr is the number
      of bytes remaining--either needing to be checked once more
      are available, or ready to be appended to or used.
   */
}


int checksum_bad(unsigned char *buf, int nc, int block_type)
{
   int ii, block_cs, cs = 0, nb;

   sermsg_init();
   if (block_type == BLOCK_NB)
      { block_cs = buf[nc-2] * 256  + buf[nc-1]; }
   else  /* BLOCK_OS */
      { block_cs = buf[nc-1] * 256  + buf[nc-2]; }
   nb = nc - 2;
   for (ii = 0; ii < nb; ii++)
   {
      cs += buf[ii];
   }
   cs %= 65536;
   if (block_cs != cs)
   {
      sermsg_cat("ERROR: checksum expected = %d,  found = %d\n", block_cs, cs);
      return -1;
   }           /*   printf("checksum: %d nb: %d \n", cs, nb); */
   return 0;
}

int GoodNMEA(char *buf)
{
   int len, i, ofs, nscan, msg_chk;
   unsigned char chk = 0;

   len = strlen(buf);
   if (len < 5 || buf[0] != '$')    return(0);
   while (buf[len-1] == '\n' || buf[len-1] == '\r')
   {
      len--;
      /* buf[len] = '\0';   */
   }
   ofs = len -3;
   nscan = sscanf(buf+ofs, "*%2x", &msg_chk);
   if (nscan != 1)      return(0);
   for (i = 1; i < len - 3; i++)
   {
      chk ^= buf[i];
   }
   /* printf("%x  %x\n", chk, msg_chk); */
   if (chk == msg_chk)
      return(1);
   return(0);
}

int get_pingnum(unsigned char *buf, int block_type)
{
   int pingnum;
   int offset;

   if (block_type == BLOCK_NB)
   {
      /* Narrowband 2-byte "Ensemble Number" is at (zero-based) offsets
         15 (MSB) and 16 (LSB) following the 14-byte header.
      */
      pingnum = buf[30] + 256 * buf[29];
   }
   else if (block_type == BLOCK_OS)
   {
      /* Broadband and OS files have the same general structure,
         and this should work for both.  With zero-based indexing,
         the offset of the second data type (variable leader) is
         in bytes 8 and 9 (little-endian).  Within the variable
         leader, bytes 2, 3, and 11 (lsb to msb) hold the "ensemble
         number".
      */
      offset = buf[8] + 256 * buf[9];
      pingnum = buf[offset + 2] + 256 * buf[offset + 3]
                                 + 65536 * buf[offset + 11];
   }
   else /* BLOCK_SON */
   {
      pingnum = buf[14] + buf[15] * 256 + buf[16] * 65536
                                        + buf[17] * 16777216;
   }
   return pingnum;
}

int BCD(unsigned char int1)
{
   return( (int1 >> 4) * 10 + (int1 & 0x0F) );
}


double get_pingtime(unsigned char *buf, int block_type)
{
   struct tm t;
   int sec_hundredths;
   time_t unix_seconds;
   double dday;

   if (block_type == BLOCK_SON)
   {
      t.tm_year = buf[18] + 256 * buf[19] - 1900;
      t.tm_mday = buf[20];
      t.tm_mon  = buf[21] - 1; /* zero-based month count */
      t.tm_min  = buf[22];
      t.tm_hour = buf[23];
      t.tm_sec  = buf[25];
      sec_hundredths = buf[24];
      unix_seconds = mktime(&t);
      dday = (difftime(unix_seconds, t_epoch)
                  + sec_hundredths / 100.0) / 86400.0;
   }
   else if (block_type == BLOCK_NB)
   {
      t.tm_year = tm_epoch.tm_year;
      t.tm_mon  = BCD(buf[14]) - 1;
      t.tm_mday = BCD(buf[15]);
      t.tm_hour = BCD(buf[16]);
      t.tm_min  = BCD(buf[17]);
      t.tm_sec  = BCD(buf[18]);
      unix_seconds = mktime(&t);
      dday = (difftime(unix_seconds, t_epoch)) / 86400.0;
   }
   else if (block_type == BLOCK_OS)
   {
      /* int n_datatypes = buf[5];  */
      int offset, time_ofs;
      unsigned char *tp;

      offset = buf[8] + 256 * buf[9];  /* variable leader */
      time_ofs = offset + 4;
      tp = buf + time_ofs;

      t.tm_year = tp[0] + 100; /* year minus 1900 for OS; maybe not for BB */
      t.tm_mon  = tp[1] - 1;
      t.tm_mday = tp[2];
      t.tm_hour = tp[3];
      t.tm_min  = tp[4];
      t.tm_sec  = tp[5];
      sec_hundredths = tp[6];
      unix_seconds = mktime(&t);
      dday = (difftime(unix_seconds, t_epoch)
                  + sec_hundredths / 100.0) / 86400.0;

   }
   else
   {
      sermsg_cat("ERROR: unsupported block_type in get_pingtime\n");
      dday = -9999.0;  /* should never happen... */
   }
   return dday;

}


