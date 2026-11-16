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

func nonce() uint32 {
	var value uint32
	for range 8 {
		c := uartGet()
		var digit byte
		switch {
		case c >= '0' && c <= '9':
			digit = c - '0'
		case c >= 'a' && c <= 'f':
			digit = c - 'a' + 10
		default:
			panic("invalid nonce")
		}
		value = value<<4 | uint32(digit)
	}
	if uartGet() != '\r' {
		panic("invalid terminator")
	}
	return value
}

const rounds = 96
const wordsPerBuffer = 256

type payload struct {
	tag   uint32
	words [64]uint32
}

type result struct {
	core     uint32
	checksum uint32
}

//go:noinline
func makePayload(seed uint32) *payload {
	p := &payload{tag: seed}
	for i := range p.words {
		p.words[i] = seed ^ uint32(i)*0x9e3779b9
	}
	return p
}

//go:noinline
func makeInterior(seed uint32) *uint32 {
	words := new([64]uint32)
	words[37] = seed ^ 0x13579bdf
	return &words[37]
}

//go:noinline
func makeBuffer(seed uint32) []uint32 {
	buf := make([]uint32, wordsPerBuffer)
	for i := range buf {
		buf[i] = seed + uint32(i)*17
	}
	return buf
}

//go:noinline
func checksum(buf []uint32) uint32 {
	var total uint32
	for _, v := range buf {
		total += v
	}
	return total
}

func worker(core int, seed uint32, ready chan<- uint32, start <-chan struct{}, done chan<- result) {
	machine.AssignCore(core)
	live := makePayload(seed ^ uint32(core))
	interior := makeInterior(seed ^ uint32(core))
	ready <- machine.CogID()
	<-start
	var total uint32
	for round := range uint32(rounds) {
		key := seed ^ uint32(core)*0x10203 ^ round*0x01010101
		first := makeBuffer(key)
		second := makeBuffer(key ^ 0x55aa55aa)
		before := checksum(first) ^ checksum(second)
		if round%4 == 0 {
			runtime.GC()
		}
		var arithmetic uint32
		for i := range uint32(12) {
			a := uint64(key+i)<<32 | uint64(key^i^0xa5a5a5a5)
			b := uint64((key & 0xffff) + i + 1)
			q, r := a/b, a%b
			arithmetic += uint32(q) ^ uint32(q>>32) ^ uint32(r)
			if q*b+r != a || r >= b {
				panic("GC corrupted arithmetic")
			}
		}
		if live.tag != seed^uint32(core) || *interior != live.tag^0x13579bdf {
			println("FAIL LIVE", core, round, live.tag, seed^uint32(core), *interior,
				(seed^uint32(core))^0x13579bdf, uintptr(unsafe.Pointer(live)), uintptr(unsafe.Pointer(interior)))
			panic("GC lost live payload")
		}
		if checksum(first)^checksum(second) != before {
			panic("GC lost live buffer")
		}
		total += before ^ round ^ arithmetic
		if round%8 == 0 {
			time.Sleep(time.Microsecond * time.Duration(core+1))
		}
		runtime.KeepAlive(live)
	}
	done <- result{machine.CogID(), total}
}

func main() {
	println("READY P2GC1")
	seed := nonce()
	println("BEGIN", seed)
	var before runtime.MemStats
	runtime.ReadMemStats(&before)
	ready := make(chan uint32, 8)
	start := make(chan struct{})
	done := make(chan result, 8)
	var finished uint32
	go func() {
		time.Sleep(300 * time.Second)
		if atomic.LoadUint32(&finished) == 0 {
			panic("GC stress timeout")
		}
	}()
	for core := range 8 {
		go worker(core, seed, ready, start, done)
	}
	var readyMask uint32
	for range 8 {
		readyMask |= 1 << <-ready
	}
	if readyMask != 255 {
		panic("GC stress missing cog")
	}
	close(start)
	ticker := time.NewTicker(time.Second)
	var mask, total uint32
	for completed := 0; completed < 8; {
		select {
		case r := <-done:
			mask |= 1 << r.core
			total += r.checksum
			completed++
		case <-ticker.C:
			runtime.GC()
			runtime.Gosched()
		}
	}
	ticker.Stop()
	atomic.StoreUint32(&finished, 1)
	runtime.GC()
	var after runtime.MemStats
	runtime.ReadMemStats(&after)
	allocated := after.TotalAlloc - before.TotalAlloc
	cycles := after.NumGC - before.NumGC
	frees := after.Frees - before.Frees
	if mask != 255 || allocated < 1<<20 || cycles < 100 || frees == 0 {
		println("FAIL GC", mask, allocated, cycles, frees)
		panic("GC did not reclaim heap")
	}
	println("GCSTRESS", mask, total, cycles, allocated, frees)
	println("DONE P2GC1", seed)
	for {
		time.Sleep(time.Second)
	}
}
