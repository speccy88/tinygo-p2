//go:build p2

package runtime

import "unsafe"

//export __atomic_load
func p2AtomicLoad(size uintptr, ptr, result unsafe.Pointer, ordering uintptr) {
	mask := lockAtomics()
	for i := uintptr(0); i < size; i++ {
		*(*byte)(unsafe.Add(result, i)) = *(*byte)(unsafe.Add(ptr, i))
	}
	unlockAtomics(mask)
}

//export __atomic_store
func p2AtomicStore(size uintptr, ptr, value unsafe.Pointer, ordering uintptr) {
	mask := lockAtomics()
	for i := uintptr(0); i < size; i++ {
		*(*byte)(unsafe.Add(ptr, i)) = *(*byte)(unsafe.Add(value, i))
	}
	unlockAtomics(mask)
}

//export __atomic_exchange
func p2AtomicExchange(size uintptr, ptr, value, result unsafe.Pointer, ordering uintptr) {
	mask := lockAtomics()
	for i := uintptr(0); i < size; i++ {
		old := *(*byte)(unsafe.Add(ptr, i))
		*(*byte)(unsafe.Add(ptr, i)) = *(*byte)(unsafe.Add(value, i))
		*(*byte)(unsafe.Add(result, i)) = old
	}
	unlockAtomics(mask)
}

//export __atomic_compare_exchange
func p2AtomicCompareExchange(size uintptr, ptr, expected, desired unsafe.Pointer, successOrder, failureOrder uintptr) bool {
	mask := lockAtomics()
	match := true
	for i := uintptr(0); i < size; i++ {
		if *(*byte)(unsafe.Add(ptr, i)) != *(*byte)(unsafe.Add(expected, i)) {
			match = false
			break
		}
	}
	if match {
		for i := uintptr(0); i < size; i++ {
			*(*byte)(unsafe.Add(ptr, i)) = *(*byte)(unsafe.Add(desired, i))
		}
	} else {
		for i := uintptr(0); i < size; i++ {
			*(*byte)(unsafe.Add(expected, i)) = *(*byte)(unsafe.Add(ptr, i))
		}
	}
	unlockAtomics(mask)
	return match
}

//export __sync_synchronize
func p2AtomicFence() {
	mask := lockAtomics()
	unlockAtomics(mask)
}
