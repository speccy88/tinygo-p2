package main

import (
	"machine"
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

type record struct{ value uint32 }

func catch(seed uint32) (value uint32) {
	witness := &record{value: seed}
	defer func() {
		p := recover().(*record)
		if p != witness {
			panic("recovery identity changed")
		}
		value = p.value
	}()
	panic(witness)
}

func catchBounds(index int) (caught bool) {
	defer func() { caught = recover() != nil }()
	values := [2]uint32{17, 29}
	println("UNEXPECTED", values[index])
	return
}

func ordered(seed uint32) (value uint32) {
	defer func() {
		if recover() == nil {
			panic("nested recovery missing")
		}
		value = value*10 + 3
	}()
	defer func() { value = value*10 + 2 }()
	defer func() { value = value*10 + 1 }()
	panic(seed)
}

func main() {
	println("READY P2RECOVER1")
	seed := nonce()
	println("BEGIN", seed)
	if catch(seed) != seed || ordered(seed) != 123 || !catchBounds(int(seed&255)+2) {
		panic("recovery failed")
	}
	done := make(chan uint32, 8)
	for core := range 8 {
		go func() {
			machine.AssignCore(core)
			for round := range uint32(16) {
				key := seed ^ uint32(core) ^ round
				if catch(key) != key || ordered(key) != 123 {
					panic("multicog recovery failed")
				}
			}
			done <- machine.CogID()
		}()
	}
	var mask uint32
	for range 8 {
		mask |= 1 << <-done
	}
	if mask != 255 {
		panic("recovery missing cog")
	}
	println("RECOVER", seed, mask, 123)
	println("DONE P2RECOVER1", seed)
	for {
		time.Sleep(time.Second)
	}
}
