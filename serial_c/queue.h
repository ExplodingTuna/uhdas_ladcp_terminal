#include <pthread.h>
#include <stdio.h>

#define QUEUE_FULL 1
#define QUEUE_ITEM_TOO_BIG 2
#define QUEUE_ITEM_EMPTY 3
#define QUEUE_REALLOCATION_FAILURE 4

struct queue_item {
   int N;              /* allocated size */
   int n_bytes;        /* bytes used */
   void *data_ptr;
};

struct queue {
   int N;
   pthread_mutex_t mutex;
   pthread_cond_t cond;
   int i_next_add;
   int i_next_remove;
   int n_waiting;
   struct queue_item **list_ptr;
};

struct queue *queue_create(int n_items, int n_bytes);
void queue_destroy(struct queue *q_ptr);
int queue_put(struct queue *q_ptr, void *buf, int n_bytes);
int queue_get(struct queue *q_ptr, void *buf, int *n_bytes_ptr, int bufsize);
void queue_print(struct queue *q_ptr, FILE *fp);


