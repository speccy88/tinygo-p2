//go:build p2
// +build p2

// Package main is Gate 2E's normal TinyGo serial challenge application.
package main

import (
	"example.com/p2goapp/bootpkg"
	_ "unsafe"
)

var bootOrder = "uninitialized"

// Keep the serial application's fixed working storage in BSS. This avoids
// pulling a memset helper into the deliberately freestanding target.
var serialState challengeState
var serialLine [64]byte
var serialOut [4]uint32

func init() {
	if bootpkg.State == 0x5032494e {
		bootOrder = "imported-init"
	} else {
		bootOrder = "bad-import-init"
	}
	writeText("P2 PHASE2 INIT\r\n")
}

// raw_p2_uart_getc is the sole receive primitive. C only configures/polls the
// console smart pin; framing, parsing, dispatch, state, and formatting are Go.
//go:linkname raw_p2_uart_getc raw_p2_uart_getc
func raw_p2_uart_getc() byte

//go:linkname raw_p2_uart_putc raw_p2_uart_putc
func raw_p2_uart_putc(c byte)

func writeText(s string) {
	for i := 0; i < len(s); i++ {
		raw_p2_uart_putc(s[i])
	}
}

func writeHex(v uint32) {
	const digits = "0123456789abcdef"
	for shift := uint32(28); ; shift -= 4 {
		raw_p2_uart_putc(digits[(v>>shift)&15])
		if shift == 0 {
			return
		}
	}
}

func writeReply(out *[4]uint32) {
	writeText("R E ")
	writeHex(out[0])
	raw_p2_uart_putc(' ')
	writeHex(out[1])
	raw_p2_uart_putc(' ')
	writeHex(out[2])
	raw_p2_uart_putc(' ')
	writeHex(out[3])
	writeText("\r\n")
}

func main() {
	if bootOrder != "imported-init" {
		writeText("P2 PHASE2 CHECK FAIL\r\n")
		for {
		}
	}
	writeText("READY P2E 1\r\n")
	for {
		length := uint32(0)
		overflow := uint32(0)
		for {
			c := raw_p2_uart_getc()
			if c == '\r' || c == '\n' {
				break
			}
			if length < 64 {
				serialLine[length] = c
				length++
			} else {
				overflow = 1
			}
		}
		if overflow != 0 {
			writeText("ERR INPUT\r\n")
			continue
		}
		bad := uint32(0)
		processChallenge(&serialLine, length, &serialState, &serialOut, &bad)
		if bad != 0 {
			writeText("ERR INPUT\r\n")
		} else {
			writeReply(&serialOut)
		}
	}
}
