

#include <stdlib.h>
#include <string.h>

#include "queue.h"  /* includes pthread.h */

void queue_print(struct queue *q_ptr, FILE *fp)
{
   int i;
   struct queue_item *item_ptr;

   pthread_mutex_lock(&(q_ptr->mutex));

   fprintf(fp, "N= %d, i_next_add= %d, i_next_remove= %d, n_waiting= %d\n",
               q_ptr->N, q_ptr->i_next_add, q_ptr->i_next_remove,
               q_ptr->n_waiting);
   for (i = 0; i < q_ptr->N; i++)
   {
      item_ptr = q_ptr->list_ptr[i];
      fprintf(fp, "i= %d, n_bytes= %d\n", i, item_ptr->n_bytes);
   }
   pthread_mutex_unlock(&(q_ptr->mutex));
}


/* Error handling is minimal, on the assumption that if this
   fails the program will abort, so we don't need to free
   any allocated memory.
*/
struct queue *queue_create(int n_items, int n_bytes)
{
   struct queue *q_ptr;
   int i;

   q_ptr = calloc(1, sizeof(struct queue));
   if (q_ptr == NULL) return NULL;
   q_ptr->list_ptr = calloc(n_items, sizeof(void*));
   if (q_ptr->list_ptr == NULL) return NULL;
   q_ptr->N = n_items;
   q_ptr->i_next_add = 0;
   q_ptr->i_next_remove = 0;
   q_ptr->n_waiting = 0;
   pthread_cond_init(&q_ptr->cond, NULL);   /* always returns 0 */
   pthread_mutex_init(&q_ptr->mutex, NULL); /* always returns 0 */
   for (i = 0; i < n_items; i++)
   {
      q_ptr->list_ptr[i] =
             (struct queue_item *) calloc(1, sizeof(struct queue_item));
      if (q_ptr->list_ptr[i] == NULL) return NULL;
      q_ptr->list_ptr[i]->data_ptr = calloc(1, n_bytes);
      if (q_ptr->list_ptr[i]->data_ptr == NULL) return NULL;
      q_ptr->list_ptr[i]->N = n_bytes;
      q_ptr->list_ptr[i]->n_bytes = 0;
   }
   return q_ptr;
}

void queue_destroy(struct queue *q_ptr)
{
   int i;

   pthread_cond_destroy(&q_ptr->cond); /* ignore EBUSY possibility */
   pthread_mutex_destroy(&q_ptr->mutex);
   for (i = 0; i < q_ptr->N; i++)
   {
      free(q_ptr->list_ptr[i]->data_ptr);
      free(q_ptr->list_ptr[i]);
   }
   free(q_ptr->list_ptr);
   free(q_ptr);
}


int queue_put(struct queue *q_ptr, void *buf, int n_bytes)
{
   int n;
   struct queue_item *item_ptr;

   if (n_bytes <= 0) return 0;  /* sanity check */
   pthread_mutex_lock(&(q_ptr->mutex));
   if (q_ptr->n_waiting >= q_ptr->N)  /* should never be greater than N... */
   {
      pthread_mutex_unlock(&(q_ptr->mutex));
      return QUEUE_FULL;
   }

   item_ptr = q_ptr->list_ptr[q_ptr->i_next_add];
#if 0
   /* Reallocate if it is too large or too small. */
   if ((n_bytes > item_ptr->N) || (n_bytes < item_ptr->N / 2))
#else
   /* Only reallocate if it is too small. */
   /* printf("n_bytes %d   item_ptr->N  %d\n", n_bytes, item_ptr->N); */
   if ((n_bytes > item_ptr->N))
#endif
   {
      void *new_data;
      n = n_bytes + n_bytes/4 + 9;     /* at least 10 bytes */
      new_data = realloc(item_ptr->data_ptr, n);
      if (new_data == NULL)
      {
         fprintf(stderr, "nbytes=%d, n=%d, N=%d\n",
                           n_bytes, n, item_ptr->N);
         pthread_mutex_unlock(&(q_ptr->mutex));
         return QUEUE_REALLOCATION_FAILURE;
      }
      item_ptr->data_ptr = new_data;
      item_ptr->N = n;
      /* printf("n_bytes %d   item_ptr->N  %d\n", n_bytes, item_ptr->N); */
   }

   memcpy(item_ptr->data_ptr, buf, n_bytes);
   item_ptr->n_bytes = n_bytes;
   q_ptr->i_next_add++;
   q_ptr->i_next_add %= q_ptr->N;
   q_ptr->n_waiting++;
   pthread_cond_signal(&(q_ptr->cond));
   pthread_mutex_unlock(&(q_ptr->mutex));
   return 0;
}


int queue_get(struct queue *q_ptr, void *buf, int *n_bytes_ptr, int bufsize)
{
   struct queue_item *item_ptr;
   int ret = 0;

   pthread_mutex_lock(&(q_ptr->mutex));
   while (q_ptr->n_waiting == 0)
   {
      pthread_cond_wait(&(q_ptr->cond), &(q_ptr->mutex));
   }
   item_ptr = q_ptr->list_ptr[q_ptr->i_next_remove];
   if (item_ptr->n_bytes > bufsize)
   {
      ret = QUEUE_ITEM_TOO_BIG;
      *n_bytes_ptr = 0;
      /* If the item is too large for the buffer, we
      throw it away entirely. */
   }
   else
   {
      *n_bytes_ptr = item_ptr->n_bytes;
      memcpy(buf, item_ptr->data_ptr, item_ptr->n_bytes);
   }
   item_ptr->n_bytes = 0;
   q_ptr->i_next_remove++;
   q_ptr->i_next_remove %= q_ptr->N;
   q_ptr->n_waiting--;
   pthread_mutex_unlock(&(q_ptr->mutex));
   return ret;
}

