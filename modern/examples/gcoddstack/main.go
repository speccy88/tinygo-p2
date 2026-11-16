package main

/*
#include <stdint.h>

extern void *p2_gc_odd_allocate(uint32_t seed);
extern void p2_gc_odd_collect(volatile uint8_t *marker);

static __attribute__((noinline)) void p2_gc_observe_churn(uint32_t *pointer) {
    __asm__ volatile ("" :: "r"(pointer) : "memory");
}

static __attribute__((noinline)) void p2_gc_wipe_dead_frames(void) {
    // Remove stale allocator roots above the caller's live stack frame.
    volatile uint8_t bytes[1536];
    for (unsigned i = 0; i < sizeof bytes; i++) bytes[i] = 0;
}

static __attribute__((noinline)) uint32_t p2_gc_odd_frame(uint32_t seed) {
    volatile uint8_t marker = (uint8_t)seed;
    uint32_t *payload = (uint32_t *)p2_gc_odd_allocate(seed);
    p2_gc_wipe_dead_frames();
    p2_gc_odd_collect(&marker);
    return *payload ^ ((uint32_t)marker << 24);
}
*/
import "C"

import (
	"runtime"
	"time"
	"unsafe"
)

var churnRoot *uint32
var observedMarker byte

// C receives the only live pointer; C malloc uses manual, uncollected storage.
//
//export p2_gc_odd_allocate
func allocatePayload(seed uint32) unsafe.Pointer {
	payload := new(uint32)
	*payload = seed ^ 0x13579bdf
	return unsafe.Pointer(payload)
}

//export p2_gc_odd_collect
func collectPayload(marker *byte) {
	observedMarker = *marker
	runtime.GC()
	for i := range uint32(128) {
		churnRoot = new(uint32)
		*churnRoot = 0xdead0000 | i
		C.p2_gc_observe_churn((*C.uint32_t)(unsafe.Pointer(churnRoot)))
	}
	runtime.GC()
}

//export raw_p2_uart_getc
func uartGet() byte

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

func main() {
	println("READY P2GCODD1")
	seed := nonce()
	println("BEGIN", seed)
	var total uint32
	for round := range uint32(32) {
		key := seed ^ round*0x9e3779b9
		value := uint32(C.p2_gc_odd_frame(C.uint32_t(key)))
		want := key ^ 0x13579bdf ^ uint32(byte(key))<<24
		if value != want || observedMarker != byte(key) {
			println("FAIL ODDGC", round, value, want, observedMarker, byte(key))
			panic("GC lost unaligned C spill root")
		}
		total += value
	}
	println("ODDGC", total, 32)
	println("DONE P2GCODD1", seed)
	for {
		time.Sleep(time.Second)
	}
}
