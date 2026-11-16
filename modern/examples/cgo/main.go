package main

/*
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t a;
    uint32_t b;
    uint64_t c;
} p2_result;

static __attribute__((noinline)) p2_result p2_mixed(
        uint32_t a, uint64_t b, uint32_t c, uint64_t d) {
    p2_result result;
    result.a = (a ^ (uint32_t)b) + c;
    result.b = ((uint32_t)(b >> 32) ^ (uint32_t)d) ^ c;
    result.c = (b + d) ^ (((uint64_t)a << 32) | c);
    return result;
}

static __attribute__((noinline)) uint64_t p2_fold(p2_result value, uint32_t salt) {
    return value.c ^ (((uint64_t)value.a << 32) | value.b) ^ salt;
}

static __attribute__((noinline)) uint64_t p2_mutate_copy(p2_result value, uint32_t salt) {
    volatile p2_result *local = &value;
    local->a ^= salt;
    local->b += 7u;
    local->c += 0x0102030405060708ULL;
    return p2_fold(value, salt);
}

typedef struct {
    uint32_t head;
    uint64_t middle;
    uint32_t tail;
} p2_layout;

static __attribute__((noinline)) p2_layout p2_make_layout(uint32_t seed) {
    p2_layout value;
    value.head = seed ^ 0x22222222u;
    value.middle = ((uint64_t)seed << 32) | (seed + 0x11111111u);
    value.tail = seed ^ 0x33333333u;
    return value;
}

static __attribute__((noinline)) uint64_t p2_layout_fold(p2_layout value) {
    return value.middle ^ (((uint64_t)value.head << 32) | value.tail);
}

enum { p2_layout_size = sizeof(p2_layout), p2_layout_middle = offsetof(p2_layout, middle), p2_layout_tail = offsetof(p2_layout, tail) };

static __attribute__((noinline)) double p2_fraction(uint32_t seed) {
    return (double)(seed & 1023u) * 0.25 + 13.5;
}

static __attribute__((noinline)) uint32_t p2_mutate(uint8_t *data, size_t size, uint32_t seed) {
    uint32_t checksum = seed;
    for (size_t i = 0; i < size; ++i) {
        data[i] = (uint8_t)((data[i] ^ (uint8_t)(seed >> ((i & 3u) * 8u))) + i * 3u);
        checksum = ((checksum << 5) | (checksum >> 27)) ^ data[i];
    }
    return checksum;
}
*/
import "C"

import (
	"time"
	"unsafe"
)

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
	println("READY P2CGO1")
	seed := nonce()
	println("BEGIN", seed)
	b := uint64(seed)<<32 | uint64(seed^0xa5a5a5a5)
	c := seed*17 + 3
	d := uint64(seed^0x01234567)<<32 | uint64(seed+0x89abcdef)
	result := C.p2_mixed(C.uint32_t(seed), C.uint64_t(b), C.uint32_t(c), C.uint64_t(d))
	folded := uint64(C.p2_fold(result, C.uint32_t(seed^0xfedcba98)))
	scaled := int64(float64(C.p2_fraction(C.uint32_t(seed))) * 4)
	var buffer [41]byte
	for i := range buffer {
		buffer[i] = 0xa5
	}
	for i := 0; i < 33; i++ {
		buffer[i+4] = byte(seed + uint32(i)*7)
	}
	checksum := uint32(C.p2_mutate((*C.uint8_t)(unsafe.Pointer(&buffer[4])), C.size_t(33), C.uint32_t(seed)))
	for i := 0; i < 4; i++ {
		if buffer[i] != 0xa5 || buffer[i+37] != 0xa5 {
			panic("Cgo buffer guard corruption")
		}
	}
	for i := 0; i < 33; i++ {
		want := byte((byte(seed+uint32(i)*7) ^ byte(seed>>(uint(i&3)*8))) + byte(i*3))
		if buffer[i+4] != want {
			panic("Cgo buffer mutation mismatch")
		}
	}
	println("CGO", uint32(result.a), uint32(result.b), uint64(result.c), folded, scaled, checksum, buffer[4], buffer[36])
	original := result
	salt := seed ^ 0x76543210
	mutated := uint64(C.p2_mutate_copy(result, C.uint32_t(salt)))
	if result != original {
		panic("Cgo by-value mutation changed caller")
	}
	println("CGOCOPY", mutated, uint32(result.a), uint32(result.b), uint64(result.c))
	layout := C.p2_make_layout(C.uint32_t(seed))
	if unsafe.Sizeof(layout) != C.p2_layout_size || unsafe.Offsetof(layout.middle) != C.p2_layout_middle ||
		unsafe.Offsetof(layout.tail) != C.p2_layout_tail {
		println("FAIL LAYOUT", unsafe.Sizeof(layout), C.p2_layout_size, unsafe.Offsetof(layout.middle),
			C.p2_layout_middle, unsafe.Offsetof(layout.tail), C.p2_layout_tail)
		panic("Cgo C/Go structure layouts differ")
	}
	println("CGOLAYOUT", C.p2_layout_size, C.p2_layout_middle, C.p2_layout_tail,
		uint32(layout.head), uint64(layout.middle), uint32(layout.tail), uint64(C.p2_layout_fold(layout)))
	println("DONE P2CGO1", seed)
	for {
		time.Sleep(time.Second)
	}
}
