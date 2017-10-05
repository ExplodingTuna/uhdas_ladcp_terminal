
#include "clocks.h"

#define FNAME_DD 0
#define FNAME_SEC 1
#define FNAME_HHMMSS 2
#define FNAME_JYD 3

#define BLOCK_NB 1
#define BLOCK_OS 2
#define BLOCK_SON 3

#define NBUF 8192  /* 4096 is too small for OS with BB/NB */

#define NPORTNAME 20


typedef struct {
   time_t time_opened,
          time_to_open,
          time;
   int    time_usec;
   int minute_interval,
       hour_interval;
   FILE *fp;
   long offset;
   char fname_ext[32];
   char fname_start[32];
   char fname_path[256];
   char fname[128];
   char mode[6];
   int flush;
   int bufmode;
   int fname_method;
}  LOGFILE_TYPE;


typedef struct {
   char name[NPORTNAME];
   char devname[NPORTNAME+5];   /* prepends /dev/  */
   char lockfile[NPORTNAME+15]; /* prepends /var/lock/LCK..  */
   struct termios def_termios, cur_termios;
   int fd;
}  SERIAL_PORT_TYPE;

char *get_ser_msg(void);

void release_port(void);
SERIAL_PORT_TYPE *acquire_port(char *port_name);

void set_time_constants(int year);

LOGFILE_TYPE *make_logfile(void);
void destroy_logfile(LOGFILE_TYPE *lf_ptr);
FILE *get_fp(LOGFILE_TYPE *lf_ptr, struct timeval t);
int ser_speed(char *speed_string);
void catch_sigterm(int sig);
int OS_ping(int fd);
int NB_ping(int fd);
FILE *fopen_outfile(char *outfilename);
int open_infile(char *infilename);
void sermsg(char *msg, int to_status, int to_errlog, int to_stderr);
int setup_sermsg(LOGFILE_TYPE *lf_ptr, FILE *fp);
void sermsg_cat(char *fmt, ...);
void sermsg_init(void);
int flush_input (int fd, int tenths, struct termios *t_ptr, double timeout);

int block_size(unsigned char *buf, int nc, int block_type);
int shift_to_start(unsigned char *buf, int *nc_ptr, int block_type);

int checksum_bad(unsigned char *buf, int nc, int block_type);

int GoodNMEA(char *buf);

int get_pingnum(unsigned char *buf, int block_type);
double get_pingtime(unsigned char *buf, int block_type);

int write_line(LOGFILE_TYPE *lf_ptr, char *buf, int nb,
               struct clocks t, int time_tag);

int zmq_broadcast(void *publisher, char *buf, int nb, struct clocks t,
                  int time_tag);
int acquire_zmq_lock(char *transport_name);
void release_zmq_lock(void);

int write_block(LOGFILE_TYPE *ens_ptr,
                LOGFILE_TYPE *log_ptr,
                LOGFILE_TYPE *binlog_ptr,
                unsigned char *buf, int nb,
                struct clocks t,
                char *logmsg);

int set_rt(int sched_rr, int lockmem, int drop_priv);

