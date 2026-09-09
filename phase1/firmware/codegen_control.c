/* Compiler-only C control, never evidence of Go execution. No libraries needed. */
_Static_assert(sizeof(unsigned int) == 4, "P2 word must be 32 bits");
unsigned int c_add(unsigned int a, unsigned int b) { return a + b; }
