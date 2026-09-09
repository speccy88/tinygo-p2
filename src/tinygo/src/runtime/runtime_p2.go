//go:build p2
// +build p2

// P2's LLVM backend is reached through the supported linux/arm surrogate so
// that TinyGo 0.23's standard library loader can operate.  The p2 build tag
// excludes ARM runtime/assembly files and selects this P2 ABI implementation.
package runtime

import "unsafe"

const GOARCH = "p2"
const TargetBits = 32
const baremetal = true

type timeUnit int64

func align(ptr uintptr) uintptr { return (ptr + 3) &^ 3 }

func getCurrentStackPointer() uintptr { return uintptr(stacksave()) }

// main is the C ABI entry called by p2_start.c after Hub RAM initialization.
// scheduler_none.run remains the only scheduler path: initHeap, initAll, main.
//export main
func main() {
	run()
}

// raw_p2_uart_putc is a thin P2 UART primitive implemented by p2_start.c.
//go:linkname raw_p2_uart_putc raw_p2_uart_putc
func raw_p2_uart_putc(c byte)

func putchar(c byte) { raw_p2_uart_putc(c) }

// This milestone deliberately has no clock driver. Time users fail loudly
// rather than returning a fabricated frozen timestamp.
func ticksToNanoseconds(t timeUnit) int64  { abort(); return 0 }
func nanosecondsToTicks(ns int64) timeUnit { abort(); return 0 }
func ticks() timeUnit                      { abort(); return 0 }
func sleepTicks(d timeUnit)                { abort() }

func exit(code int) { abort() }
func abort() {
	for {
		p2_halt()
	}
}

//go:linkname p2_halt p2_halt
func p2_halt()

// Keep unsafe imported in this target runtime: baremetal.go owns linker
// symbols/heap ABI, while this file owns P2-specific runtime entry and ABI.
var _ unsafe.Pointer
