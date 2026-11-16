package main

import (
	"machine"
	"time"
)

func main() {
	if err := machine.PSRAM.Configure(); err != nil {
		panic(err)
	}
	message := []byte("Hello from 32 MiB of PSRAM!")
	const address = 1024
	if _, err := machine.PSRAM.WriteAt(message, address); err != nil {
		panic(err)
	}
	readback := make([]byte, len(message))
	if _, err := machine.PSRAM.ReadAt(readback, address); err != nil {
		panic(err)
	}
	println("External memory bytes:", machine.PSRAM.Size())
	println(string(readback))
	for {
		time.Sleep(time.Second)
	}
}
