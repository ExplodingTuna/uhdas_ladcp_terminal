
#define STRINGSET_MAX 10

struct stringset {
   int n_strings;
   char *string[STRINGSET_MAX];
   int n_char[STRINGSET_MAX];
   int count[STRINGSET_MAX];
   };

int read_stringset(struct stringset *s_ptr, int argc, char **argv, int i);

int string_found(struct stringset *s_ptr, char *buf);

int string_selected(struct stringset *s_ptr, char *buf, int nstep);
