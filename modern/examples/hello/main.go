package main

import (
	"machine"
	"runtime"
	"time"
)

type result struct {
	worker int
	cog    uint32
	sum    uint32
}

func main() {
	println("TinyGo 0.44.0 on Propeller 2")
	println("Available cogs:", runtime.NumCPU())
	completed := make(chan result, 8)
	for worker := 0; worker < 8; worker++ {
		go func(n int) {
			var sum uint32
			for i := uint32(0); i < 50000; i++ {
				sum = (sum^i)*1664525 + 1013904223
			}
			completed <- result{n, machine.CogID(), sum}
		}(worker)
	}
	for range 8 {
		r := <-completed
		println("Worker", r.worker, "ran on cog", r.cog, "checksum", r.sum)
	}
	for tick := 1; ; tick++ {
		println("Alive", tick)
		time.Sleep(time.Second)
	}
}
