// Escaping allocation negative: storing a dynamically-sized heap object in a
// global prevents stack promotion, so gc=none must leave runtime.alloc unresolved.
package main

var escaped *[]byte
var source uint32 = 17

func main() {
	n := int(source&31) + 33
	p := make([]byte, n)
	p[0] = byte(source)
	escaped = &p
	for { }
}
