package main

import (
	"machine"
	"runtime"
	"time"
)

type result struct {
	core int
	sum  uint32
}

func worker(core int, done chan<- result) {
	// Affinity is optional. Here it makes the eight-core demonstration explicit.
	machine.AssignCore(core)
	var sum uint32
	for i := uint32(1); i <= 10000; i++ {
		sum += i
		if i%256 == 0 {
			runtime.Gosched() // Let other ready goroutines on this cog run.
		}
	}
	done <- result{core: int(machine.CogID()), sum: sum}
}

func main() {
	done := make(chan result, 8)
	for core := 0; core < 8; core++ {
		go worker(core, done)
	}
	for i := 0; i < 8; i++ {
		r := <-done
		println("Cog", r.core, "sum", r.sum)
	}
	println("All eight workers finished!")
	for {
		time.Sleep(time.Second)
	}
}
