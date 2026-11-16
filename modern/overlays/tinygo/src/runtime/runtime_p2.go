//go:build p2

package runtime

import (
	"runtime/interrupt"
	"unsafe"
)

const GOARCH = "p2"
const TargetBits = 32
const deferExtraRegs = 0
const callInstSize = 4
const zeroSizeAllocPtr uintptr = 16

func align(ptr uintptr) uintptr { return (ptr + 7) &^ 7 }

func getCurrentStackPointer() uintptr { return p2StackPointer() }

//export p2_stack_pointer
func p2StackPointer() uintptr

//export p2_counter
func p2Counter() uint64

//export p2_cog_id
func p2CogID() uint32

//export p2_wait
func p2Wait()

//export raw_p2_uart_putc
func p2UARTPutc(c byte)

//export raw_p2_uart_getc
func p2UARTGetc() byte

//export raw_p2_uart_buffered
func p2UARTBuffered() int

//export p2_halt
func p2Halt()

//export main
func main() {
	// The scheduler allocates its initial goroutine before initAll. Explicit
	// unwinding can leave package initializers for runtime execution, so set
	// these linker-derived bounds before the first allocation.
	heapStart = uintptr(unsafe.Pointer(&heapStartSymbol))
	heapEnd = uintptr(unsafe.Pointer(&heapEndSymbol))
	globalsStart = uintptr(unsafe.Pointer(&globalsStartSymbol))
	globalsEnd = uintptr(unsafe.Pointer(&globalsEndSymbol))
	stackTop = uintptr(unsafe.Pointer(&stackTopSymbol))
	initP2Runtime()
	initP2GC()
	run()
	exit(0)
}

func putchar(c byte) { p2UARTPutc(c) }

func getchar() byte {
	for p2UARTBuffered() == 0 {
		Gosched()
	}
	return p2UARTGetc()
}

func buffered() int { return p2UARTBuffered() }

func ticks() timeUnit { return timeUnit(p2Counter()) }

func ticksToNanoseconds(t timeUnit) int64 {
	return int64(t)/4*25 + int64(t)%4*25/4
}

func nanosecondsToTicks(ns int64) timeUnit {
	return timeUnit(ns/25*4 + ns%25*4/25)
}

func sleepTicks(d timeUnit) {
	end := ticks() + d
	for ticks() < end {
		p2Wait()
	}
}

func waitForEvents() { p2Wait() }

func exit(code int) {
	p2Halt()
	for {
	}
}

//export abort
func abort() { exit(1) }

var procPinnedMask [8]interrupt.State

//go:linkname procPin sync/atomic.runtime_procPin
func procPin() {
	core := p2CogID()
	procPinnedMask[core] = interrupt.Disable()
}

//go:linkname procUnpin sync/atomic.runtime_procUnpin
func procUnpin() {
	interrupt.Restore(procPinnedMask[p2CogID()])
}

var _ unsafe.Pointer

func p2SerialWrite(data []byte) {
	printlock()
	for _, c := range data {
		p2UARTPutc(c)
	}
	printunlock()
}

func p2SerialWriteByte(c byte) {
	printlock()
	p2UARTPutc(c)
	printunlock()
}
