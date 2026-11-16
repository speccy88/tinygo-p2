// Hardware conformance for the modern P2 target. Results depend on a fresh
// host nonce; host-side oracles independently verify the reported arithmetic.
package main

import (
	"machine"
	"math"
	"math/bits"
	"sync"
	"sync/atomic"
	"time"
	_ "unsafe"
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

func sum[T ~uint32](values []T) T {
	var result T
	for _, value := range values {
		result += value
	}
	return result
}

func sequence(start uint32) func(func(uint32) bool) {
	return func(yield func(uint32) bool) {
		for i := range uint32(7) {
			if !yield(start + i) {
				return
			}
		}
	}
}

type number uint32

func (n number) Value() uint32 { return uint32(n) }

func interfaceValue(n interface{ Value() uint32 }) uint32 { return n.Value() }

func deferred(n uint32) (result uint32) {
	defer func() { result ^= n }()
	result = n + 13
	return
}

//go:noinline
func multiplyWide(a, b uint64) (uint64, uint64) {
	return bits.Mul64(a, b)
}

func main() {
	println("READY P2CONF1")
	seed := nonce()
	println("BEGIN", seed)
	a := uint64(seed)<<32 | uint64(seed^0xabcdef01)
	b := uint64(seed&0xffff) + 7
	println("ARITH", a/b, a%b, a*37)
	h0, l0 := multiplyWide(^uint64(0), ^uint64(0))
	multiplier := uint64(seed^0x13579bdf)<<32 | uint64(seed+0x2468ace1)
	h1, l1 := multiplyWide(a, multiplier)
	h2, l2 := multiplyWide(uint64(seed)<<32|0xffffffff, 0x1ffffffff)
	println("MUL64", h0, l0, h1, l1, h2, l2)
	values := make([]uint32, 0, 40)
	m := make(map[uint32]uint32)
	for i := range uint32(32) {
		values = append(values, seed+i)
		m[i^seed] = (seed + i) ^ (i * 17)
	}
	var mapSum uint32
	for i := range uint32(32) {
		mapSum += m[i^seed]
	}
	var iterSum uint32
	for value := range sequence(seed) {
		iterSum += value
	}
	println("LANG", sum(values), mapSum, iterSum, interfaceValue(number(seed)), deferred(seed))
	f := float64(seed&255) / 8
	println("FLOAT", uint32((f*f+0.5)*256))
	n := float64(seed&255) + 1
	root := math.Sqrt(n * n)
	x := -n - 0.25
	var mathFlags uint32
	if math.Abs(math.Log(math.Exp(n/256))-n/256) < 1e-9 {
		mathFlags |= 1
	}
	if math.IsNaN(math.Float64frombits(0x7ff8000000000000 | uint64(seed))) {
		mathFlags |= 2
	}
	if math.IsInf(math.Inf(1), 1) && math.IsInf(math.Inf(-1), -1) && !math.IsInf(n, 0) {
		mathFlags |= 4
	}
	println("MATH", uint32(root), int32(math.Floor(x)), int32(math.Ceil(x)), int32(math.Trunc(x)), mathFlags)
	startTime := time.Now()
	time.Sleep(2 * time.Millisecond)
	elapsed := time.Since(startTime)
	if elapsed < 2*time.Millisecond || elapsed > 2*time.Second {
		panic("time duration invalid")
	}
	println("TIME", elapsed.Microseconds())
	ready := make(chan uint32, 8)
	start := make(chan struct{})
	done := make(chan uint32, 8)
	var active, peak int32
	var atomicTotal uint32
	var mutex sync.Mutex
	var lockedTotal uint32
	for core := range 8 {
		go func() {
			machine.AssignCore(core)
			ready <- machine.CogID()
			<-start
			current := atomic.AddInt32(&active, 1)
			for {
				previous := atomic.LoadInt32(&peak)
				if current <= previous || atomic.CompareAndSwapInt32(&peak, previous, current) {
					break
				}
			}
			until := time.Now().Add(20 * time.Millisecond)
			// There is deliberately no scheduler yield in this interval.
			// Concurrent active workers therefore require independent cogs.
			for time.Now().Before(until) {
			}
			atomic.AddInt32(&active, -1)
			for range 1000 {
				atomic.AddUint32(&atomicTotal, 1)
			}
			for range 100 {
				mutex.Lock()
				lockedTotal++
				mutex.Unlock()
			}
			done <- machine.CogID()
		}()
	}
	var readyMask uint32
	for range 8 {
		readyMask |= 1 << <-ready
	}
	close(start)
	var doneMask uint32
	for range 8 {
		doneMask |= 1 << <-done
	}
	if readyMask != 255 || doneMask != 255 || peak < 2 || atomicTotal != 8000 || lockedTotal != 800 {
		println("FAIL CORES", readyMask, doneMask, peak, atomicTotal, lockedTotal)
		panic("multicog validation failed")
	}
	println("CORES", readyMask, doneMask, peak, atomicTotal, lockedTotal)

	// These ordinary goroutines have no affinity assignment.
	// Their busy intervals require automatic scheduling onto multiple cogs.
	unboundReady := make(chan struct{}, 8)
	unboundStart := make(chan struct{})
	type workerResult struct{ cog, checksum uint32 }
	unboundDone := make(chan workerResult, 8)
	active, peak = 0, 0
	for worker := range uint32(8) {
		go func(worker uint32) {
			unboundReady <- struct{}{}
			<-unboundStart
			cog := machine.CogID()
			current := atomic.AddInt32(&active, 1)
			for {
				previous := atomic.LoadInt32(&peak)
				if current <= previous || atomic.CompareAndSwapInt32(&peak, previous, current) {
					break
				}
			}
			var checksum uint32
			for i := range uint32(64) {
				checksum += (seed ^ (worker * 0x10203)) + i*17
			}
			until := time.Now().Add(20 * time.Millisecond)
			for time.Now().Before(until) {
			}
			atomic.AddInt32(&active, -1)
			unboundDone <- workerResult{cog, checksum}
		}(worker)
	}
	for range 8 {
		<-unboundReady
	}
	close(unboundStart)
	var unboundMask, unboundTotal uint32
	for range 8 {
		result := <-unboundDone
		unboundMask |= 1 << result.cog
		unboundTotal += result.checksum
	}
	if unboundMask == 0 || unboundMask&(unboundMask-1) == 0 || peak < 2 {
		panic("automatic multicog scheduling failed")
	}
	println("UNBOUND", unboundMask, peak, unboundTotal)
	println("DONE P2CONF1", seed)
	for {
		time.Sleep(time.Second)
	}
}
