//go:build p2 && scheduler.cores

package runtime

import (
	"runtime/volatile"
	"unsafe"
)

const numCPU = 8
const p2SystemStackWords = 2048

var p2CoreReady [numCPU]uint32

//go:extern _p2_secondary_stacks
var p2SecondaryStacks [numCPU - 1][p2SystemStackWords]uint32

type spinLock struct{ id uint32 }

var (
	printLock     spinLock
	schedulerLock spinLock
	atomicsLock   spinLock
	futexLock     spinLock
)

//export p2_lock_new
func p2LockNew() uint32

//export p2_lock_acquire_id
func p2LockAcquire(id uint32)

//export p2_lock_release_id
func p2LockRelease(id uint32)

//export p2_start_core
func p2StartCore(core uint32, stack uintptr)

func (l *spinLock) Lock()   { p2LockAcquire(l.id) }
func (l *spinLock) Unlock() { p2LockRelease(l.id) }

func initP2Runtime() {
	printLock.id = p2LockNew()
	schedulerLock.id = p2LockNew()
	atomicsLock.id = p2LockNew()
	futexLock.id = p2LockNew()
	if printLock.id > 15 || schedulerLock.id > 15 || atomicsLock.id > 15 || futexLock.id > 15 {
		abort()
	}
}

func currentCPU() uint32 { return p2CogID() }

func startSecondaryCores() {
	for core := uint32(1); core < numCPU; core++ {
		stack := uintptr(unsafe.Pointer(&p2SecondaryStacks[core-1][0]))
		p2StartCore(core, stack)
	}
	deadline := ticks() + nanosecondsToTicks(1_000_000_000)
	for core := uint32(1); core < numCPU; core++ {
		for volatile.LoadUint32(&p2CoreReady[core]) == 0 {
			if ticks() >= deadline {
				println("P2 cog not ready:", core)
				runtimeFatal("P2 cog startup timeout")
			}
			p2Wait()
		}
	}
}

//export tinygo_runCore
func runP2Core() {
	initP2GC()
	volatile.StoreUint32(&p2CoreReady[currentCPU()], 1)
	waitForSecondaryCoresReady()
	schedulerLock.Lock()
	scheduler(false)
	schedulerLock.Unlock()
	exit(0)
}

var waitingCores uint8
var schedulerWakePending [numCPU]uint32
var sleepingCore uint8 = 0xff
var sleepWake [numCPU]uint32

func spinLoopWait() { p2Wait() }

func hasSleepingCore() bool { return sleepingCore != 0xff }

func schedulerUnlockAndWait() {
	core := currentCPU()
	waitingCores |= 1 << core
	volatile.StoreUint32(&schedulerWakePending[core], 0)
	schedulerLock.Unlock()
	for volatile.LoadUint32(&schedulerWakePending[core]) == 0 {
		p2Wait()
	}
	schedulerLock.Lock()
}

func schedulerWake() {
	for core := uint32(0); core < numCPU; core++ {
		if waitingCores&(1<<core) != 0 {
			schedulerWakeCore(core)
			return
		}
	}
	interruptSleepTicksMulticore(0)
}

func schedulerWakeCore(core uint32) {
	if waitingCores&(1<<core) != 0 {
		waitingCores &^= 1 << core
		volatile.StoreUint32(&schedulerWakePending[core], 1)
	}
	if uint32(sleepingCore) == core {
		volatile.StoreUint32(&sleepWake[core], 1)
	}
}

func sleepTicksMulticore(d timeUnit) {
	core := currentCPU()
	sleepingCore = uint8(core)
	volatile.StoreUint32(&sleepWake[core], 0)
	end := ticks() + d
	schedulerLock.Unlock()
	for volatile.LoadUint32(&sleepWake[core]) == 0 && ticks() < end {
		p2Wait()
	}
	schedulerLock.Lock()
	sleepingCore = 0xff
}

func interruptSleepTicksMulticore(wakeup timeUnit) {
	if hasSleepingCore() {
		volatile.StoreUint32(&sleepWake[sleepingCore], 1)
	}
}
