//go:build p2

package runtime

// 8-bit atomics.

//export __atomic_load_1
func __atomic_load_1(ptr *uint8, ordering uintptr) uint8 {
	// The LLVM docs for this say that there is a val argument after the pointer.
	// That is a typo, and the GCC docs omit it.
	mask := lockAtomics()
	val := *ptr
	unlockAtomics(mask)
	return val
}

//export __atomic_store_1
func __atomic_store_1(ptr *uint8, val uint8, ordering uintptr) {
	mask := lockAtomics()
	*ptr = val
	unlockAtomics(mask)
}

//go:inline
func doAtomicCAS8(ptr *uint8, expected, desired uint8) uint8 {
	mask := lockAtomics()
	old := *ptr
	if old == expected {
		*ptr = desired
	}
	unlockAtomics(mask)
	return old
}

//export __sync_val_compare_and_swap_1
func __sync_val_compare_and_swap_1(ptr *uint8, expected, desired uint8) uint8 {
	return doAtomicCAS8(ptr, expected, desired)
}

//export __atomic_compare_exchange_1
func __atomic_compare_exchange_1(ptr, expected *uint8, desired uint8, successOrder, failureOrder uintptr) bool {
	exp := *expected
	old := doAtomicCAS8(ptr, exp, desired)
	if old != exp {
		*expected = old
		return false
	}
	return true
}

//go:inline
func doAtomicSwap8(ptr *uint8, new uint8) uint8 {
	mask := lockAtomics()
	old := *ptr
	*ptr = new
	unlockAtomics(mask)
	return old
}

//export __sync_lock_test_and_set_1
func __sync_lock_test_and_set_1(ptr *uint8, new uint8) uint8 {
	return doAtomicSwap8(ptr, new)
}

//export __atomic_exchange_1
func __atomic_exchange_1(ptr *uint8, new uint8, ordering uintptr) uint8 {
	return doAtomicSwap8(ptr, new)
}

//go:inline
func doAtomicAdd8(ptr *uint8, value uint8) (old, new uint8) {
	mask := lockAtomics()
	old = *ptr
	new = old + value
	*ptr = new
	unlockAtomics(mask)
	return old, new
}

//export __atomic_fetch_add_1
func __atomic_fetch_add_1(ptr *uint8, value uint8, ordering uintptr) uint8 {
	old, _ := doAtomicAdd8(ptr, value)
	return old
}

//export __sync_fetch_and_add_1
func __sync_fetch_and_add_1(ptr *uint8, value uint8) uint8 {
	old, _ := doAtomicAdd8(ptr, value)
	return old
}

//export __atomic_add_fetch_1
func __atomic_add_fetch_1(ptr *uint8, value uint8, ordering uintptr) uint8 {
	_, new := doAtomicAdd8(ptr, value)
	return new
}

//go:inline
func doAtomicAnd8(ptr *uint8, value uint8) (old, new uint8) {
	mask := lockAtomics()
	old = *ptr
	new = old & value
	*ptr = new
	unlockAtomics(mask)
	return old, new
}

//export __atomic_fetch_and_1
func __atomic_fetch_and_1(ptr *uint8, value uint8, ordering uintptr) uint8 {
	old, _ := doAtomicAnd8(ptr, value)
	return old
}

//export __sync_fetch_and_and_1
func __sync_fetch_and_and_1(ptr *uint8, value uint8) uint8 {
	old, _ := doAtomicAnd8(ptr, value)
	return old
}

//export __atomic_and_fetch_1
func __atomic_and_fetch_1(ptr *uint8, value uint8, ordering uintptr) uint8 {
	_, new := doAtomicAnd8(ptr, value)
	return new
}

//go:inline
func doAtomicOr8(ptr *uint8, value uint8) (old, new uint8) {
	mask := lockAtomics()
	old = *ptr
	new = old | value
	*ptr = new
	unlockAtomics(mask)
	return old, new
}

//export __atomic_fetch_or_1
func __atomic_fetch_or_1(ptr *uint8, value uint8, ordering uintptr) uint8 {
	old, _ := doAtomicOr8(ptr, value)
	return old
}

//export __sync_fetch_and_or_1
func __sync_fetch_and_or_1(ptr *uint8, value uint8) uint8 {
	old, _ := doAtomicOr8(ptr, value)
	return old
}

//export __atomic_or_fetch_1
func __atomic_or_fetch_1(ptr *uint8, value uint8, ordering uintptr) uint8 {
	_, new := doAtomicOr8(ptr, value)
	return new
}
