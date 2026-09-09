//go:build p2
// +build p2
package main

import _ "unsafe"

//go:linkname raw_p2_uart_getc raw_p2_uart_getc
func raw_p2_uart_getc() byte
//go:linkname raw_p2_uart_putc raw_p2_uart_putc
func raw_p2_uart_putc(byte)
func text(s string) { for i:=0;i<len(s);i++ { raw_p2_uart_putc(s[i]) } }

func main() {
 text("P2 GO BOUNDS ARMED\r\n")
 trigger := uint32(raw_p2_uart_getc()) // serial-dependent, not compile-time known.
 text("P2 GO BOUNDS TRIGGER\r\n")
 values := [1]uint32{0xdecafbad}
 _ = values[trigger] // required checked Go bounds access; input 'X' is out of range.
 text("P2 GO BOUNDS FORBIDDEN CONTINUATION\r\n")
 for {}
}
