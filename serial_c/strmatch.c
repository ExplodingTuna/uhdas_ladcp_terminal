/* strmatch.c
   This file includes a very simple pair of routines for use in
   ser_asc: the first routine reads trailing command line arguments
   and puts them into a structure; the second uses this structure
   to check for the presence of any of the strings at the start
   of a line received by ser_asc.

   In the present implementation, the stringset structure has a
   fixed size (STRINGSET_MAX, in strmatch.h), keeping the code
   simple.

   EF some time in 2003 or early 2004.

*/


#include <string.h>
#include "strmatch.h"


int read_stringset(struct stringset *s_ptr, int argc, char **argv, int i)
{
   int ns, istring;

   if (argc - i > STRINGSET_MAX)
      return -1;

   for (istring = i, ns = 0; istring < argc; istring++, ns++)
   {
      s_ptr->string[ns] = argv[istring];
      s_ptr->n_char[ns] = strlen(argv[istring]);
      s_ptr->count[ns] = 0;
   }
   s_ptr->n_strings = ns;
   return ns;
}

int string_found(struct stringset *s_ptr, char *buf)
{
   int i;

   for (i = 0; i < s_ptr->n_strings; i++)
   {
      if (strncmp(buf, s_ptr->string[i], s_ptr->n_char[i]) == 0)
      {
         return 1;
      }
   }
   return 0;
}

int string_selected(struct stringset *s_ptr, char *buf, int nstep)
{
   int i;
   int ret = 0;

   for (i = 0; i < s_ptr->n_strings; i++)
   {
      if (strncmp(buf, s_ptr->string[i], s_ptr->n_char[i]) == 0)
      {
         /* Always start with the first match. This requires that
            we check count before incrementing it, so it makes the
            code a little more convoluted than it would otherwise be.
         */
         if (s_ptr->count[i] == 0)
         {
            ret = 1;
         }
         s_ptr->count[i]++;
         s_ptr->count[i] %= nstep;

         if (ret)
         {
            return 1;
         }
      }
   }
   return 0;
}
