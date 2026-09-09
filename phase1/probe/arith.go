// Package probe contains the complete Go payload of the first P2 experiment.
// Keep this file import-free. Hardware startup and I/O remain in C.
package probe

// P2Add adds two words modulo 2^32. The export is required for C ABI linkage.
//
//export p2_add
//go:noinline
func P2Add(a, b uint32) uint32 {
	return a + b
}

// P2Mix exercises subtraction, XOR, shifts, OR, addition and argument ordering.
//
//export p2_mix
//go:noinline
func P2Mix(a, b uint32) uint32 {
	x := a ^ b
	return ((x << 5) | (x >> 27)) + (a - b)
}
