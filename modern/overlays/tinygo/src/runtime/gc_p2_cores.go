//go:build p2 && scheduler.cores && (gc.conservative || gc.precise)

package runtime

import (
	"internal/task"
	"runtime/volatile"
	"sync/atomic"
	"unsafe"
)

var gcScanState atomic.Uint32

// R0-R31, PTRA, PTRB, PA, PB, parked, release.
var p2GCContext [numCPU][38]uint32

//export p2_gc_install
func p2GCInstall(context *uint32)

//export p2_cog_attention
func p2CogAttention(mask uint32)

//go:extern _stack_bottom
var p2StackBottomSymbol [0]byte

func initP2GC() {
	p2GCInstall(&p2GCContext[currentCPU()][0])
}

func p2SystemStackBottom(core uint32) uintptr {
	if core == 0 {
		return uintptr(unsafe.Pointer(&p2StackBottomSymbol))
	}
	return uintptr(unsafe.Pointer(&p2SecondaryStacks[core-1][0]))
}

func gcMarkReachable() {
	schedulerLock.Lock()
	core := currentCPU()
	if secondaryCoresReady.Load() != 0 {
		for other := uint32(0); other < numCPU; other++ {
			if other == core {
				continue
			}
			volatile.StoreUint32(&p2GCContext[other][37], 0)
			p2CogAttention(1 << other)
		}
		for other := uint32(0); other < numCPU; other++ {
			if other == core {
				continue
			}
			for volatile.LoadUint32(&p2GCContext[other][36]) == 0 {
				p2CogAttention(1 << other)
				p2Wait()
			}
			sp := systemStack[other]
			if sp == 0 {
				sp = uintptr(p2GCContext[other][32])
			}
			markRoots(p2SystemStackBottom(other), sp)
			// Integer snapshots are absent from the compiler-generated global roots.
			context := uintptr(unsafe.Pointer(&p2GCContext[other][0]))
			markRoots(context, context+36*unsafe.Sizeof(uint32(0)))
		}
	}
	for slot := 0; slot < 36; slot++ {
		p2GCContext[core][slot] = 0
	}
	scanCurrentStack()
	if !task.OnSystemStack() {
		markRoots(p2SystemStackBottom(core), task.SystemStack())
	}
	markGlobals()
}

//go:export tinygo_scanCurrentStack
func scanCurrentStack()

//go:export tinygo_scanstack
func scanstack(sp uintptr) {
	if task.OnSystemStack() {
		markRoots(p2SystemStackBottom(currentCPU()), sp)
	} else {
		markCurrentGoroutineStack(sp)
	}
}

func gcResumeWorld() {
	core := currentCPU()
	if secondaryCoresReady.Load() != 0 {
		for other := uint32(0); other < numCPU; other++ {
			if other == core {
				continue
			}
			volatile.StoreUint32(&p2GCContext[other][37], 1)
		}
		for other := uint32(0); other < numCPU; other++ {
			if other == core {
				continue
			}
			for volatile.LoadUint32(&p2GCContext[other][36]) != 0 {
				p2Wait()
			}
		}
	}
	schedulerLock.Unlock()
}
