package main

import (
	"machine"
	"runtime"
	"sync/atomic"
	"time"
	"unsafe"
)

//export raw_p2_uart_getc
func uartGet() byte

//export memcpy
func cMemcpy(dst, src unsafe.Pointer, length uintptr) unsafe.Pointer

//export memmove
func cMemmove(dst, src unsafe.Pointer, length uintptr) unsafe.Pointer

//export memset
func cMemset(dst unsafe.Pointer, value uint32, length uintptr) unsafe.Pointer

func nonce() uint32 {
	var value uint32
	for range 8 {
		c := uartGet()
		if c >= 'a' && c <= 'f' {
			c = c - 'a' + 10
		} else if c >= '0' && c <= '9' {
			c -= '0'
		} else {
			panic("bad nonce")
		}
		value = value<<4 | uint32(c)
	}
	if uartGet() != '\r' {
		panic("bad nonce terminator")
	}
	return value
}

//go:noinline
func goCopy(dst, src []byte) int { return copy(dst, src) }

//go:noinline
func goClear(dst []byte) { clear(dst) }

func pattern(seed uint32, index int) byte {
	return byte((seed + uint32(index)*29) ^ uint32(index>>3))
}

func mix(hash, value uint32) uint32 { return (hash<<5 | hash>>27) ^ value }

func main() {
	println("READY P2MEMORY1")
	seed := nonce()
	println("BEGIN", seed)
	machine.AssignCore(0)
	var stop, collections, ticks uint32
	ready := make(chan struct{}, 2)
	done := make(chan struct{}, 2)
	go func() {
		machine.AssignCore(7)
		ready <- struct{}{}
		for atomic.LoadUint32(&stop) == 0 {
			runtime.GC()
			atomic.AddUint32(&collections, 1)
			time.Sleep(200 * time.Microsecond)
		}
		done <- struct{}{}
	}()
	go func() {
		machine.AssignCore(6)
		ready <- struct{}{}
		for atomic.LoadUint32(&stop) == 0 {
			time.Sleep(100 * time.Microsecond)
			atomic.AddUint32(&ticks, 1)
		}
		done <- struct{}{}
	}()
	<-ready
	<-ready
	beforeGC, beforeTicks := atomic.LoadUint32(&collections), atomic.LoadUint32(&ticks)
	lengths := []int{0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 127, 128, 129, 511, 512, 513, 1023, 1024, 1025}
	var source, target [2048]byte
	guard := byte(seed ^ 0x6d)
	hash, operations := seed, uint32(0)
	for _, length := range lengths {
		for sourceAlign := range 4 {
			for targetAlign := range 4 {
				from, to := 8+sourceAlign, 8+targetAlign
				for i := range source {
					source[i], target[i] = pattern(seed, i), guard
				}
				for operation := range 3 {
					switch operation {
					case 0:
						if goCopy(target[to:to+length], source[from:from+length]) != length {
							panic("copy count")
						}
					case 1:
						goClear(target[to : to+length])
					case 2:
						p := unsafe.Pointer(&target[to])
						if cMemcpy(p, unsafe.Pointer(&source[from]), uintptr(length)) != p {
							panic("memcpy return pointer")
						}
					}
					hash = mix(hash, operations)
					operations++
					for i := range target {
						value := target[i]
						expected := guard
						inside := i >= to && i < to+length
						if inside {
							expected = pattern(seed, from+i-to)
							if operation == 1 {
								expected = 0
							}
							hash = mix(hash, uint32(value))
						}
						if value != expected || source[i] != pattern(seed, i) {
							println("BAD COPY", length, sourceAlign, targetAlign, operation, i)
							panic("copy/clear data or guard")
						}
					}
				}
			}
		}
	}
	for _, length := range lengths {
		for _, distance := range []int{1, 2, 3, 4, 127, 128, 511, 512} {
			for direction := range 2 {
				from, to := 8, 8+distance
				if direction == 1 {
					from, to = to, from
				}
				for operation := range 2 {
					for i := range target {
						target[i] = pattern(seed, i)
					}
					if operation == 0 {
						if goCopy(target[to:to+length], target[from:from+length]) != length {
							panic("overlap copy count")
						}
					} else {
						p := unsafe.Pointer(&target[to])
						if cMemmove(p, unsafe.Pointer(&target[from]), uintptr(length)) != p {
							panic("memmove return pointer")
						}
					}
					hash = mix(hash, operations)
					operations++
					for i := range target {
						value := target[i]
						expected := pattern(seed, i)
						if i >= to && i < to+length {
							expected = pattern(seed, from+i-to)
							hash = mix(hash, uint32(value))
						}
						if value != expected {
							println("BAD MOVE", length, distance, direction, operation, i)
							panic("overlap data or guard")
						}
					}
				}
			}
		}
	}
	for _, length := range lengths {
		for alignment := range 4 {
			to := 8 + alignment
			for _, fill := range []uint32{0, 0x55, 0xff, 0x80, 0x123456a7, seed} {
				for i := range target {
					target[i] = guard
				}
				p := unsafe.Pointer(&target[to])
				if cMemset(p, fill, uintptr(length)) != p {
					panic("memset return pointer")
				}
				hash = mix(hash, operations)
				operations++
				for i := range target {
					value := target[i]
					expected := guard
					if i >= to && i < to+length {
						expected = byte(fill)
						hash = mix(hash, uint32(value))
					}
					if value != expected {
						println("BAD FILL", length, alignment, fill, i)
						panic("memset data or guard")
					}
				}
			}
		}
	}
	gcDuring, ticksDuring := atomic.LoadUint32(&collections)-beforeGC, atomic.LoadUint32(&ticks)-beforeTicks
	atomic.StoreUint32(&stop, 1)
	<-done
	<-done
	if gcDuring < 2 || ticksDuring < 2 {
		println("NO STRESS", gcDuring, ticksDuring)
		panic("memory tests lacked concurrent GC/timers")
	}
	println("MEMORY", operations, hash, gcDuring, ticksDuring)
	println("DONE P2MEMORY1", seed)
	for {
		time.Sleep(time.Second)
	}
}
