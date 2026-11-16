//go:build p2 && !scheduler.cores && (gc.conservative || gc.precise)

package runtime

import (
	"internal/task"
	"sync/atomic"
	"unsafe"
)

var gcScanState atomic.Uint32

//go:extern _stack_bottom
var p2StackBottomSymbol [0]byte

func initP2GC() {}

func gcMarkReachable() {
	scanCurrentStack()
	if !task.OnSystemStack() {
		markRoots(uintptr(unsafe.Pointer(&p2StackBottomSymbol)), task.SystemStack())
	}
	markGlobals()
}

//go:export tinygo_scanCurrentStack
func scanCurrentStack()

//go:export tinygo_scanstack
func scanstack(sp uintptr) {
	if task.OnSystemStack() {
		markRoots(uintptr(unsafe.Pointer(&p2StackBottomSymbol)), sp)
	} else {
		markCurrentGoroutineStack(sp)
	}
}

func gcResumeWorld() {}
