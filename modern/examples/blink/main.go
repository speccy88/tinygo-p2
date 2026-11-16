package main

import (
	"machine"
	"time"
)

func main() {
	// P38 is an onboard LED on the P2-EC32MB. Enable the board's LED switch.
	led := machine.Pin(38)
	led.Configure(machine.PinConfig{Mode: machine.PinOutput})
	for {
		led.High()
		println("LED on")
		time.Sleep(500 * time.Millisecond)
		led.Low()
		println("LED off")
		time.Sleep(500 * time.Millisecond)
	}
}
