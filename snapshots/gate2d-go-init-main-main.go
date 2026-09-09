// Gate2D preserved source snapshot: physical imported-init/main proof.
// Original file before Gate2E serial challenge replacement.
package main

import "example.com/p2goapp/bootpkg"

var bootOrder = "uninitialized"
var signedGlobal int32 = -7
var words = [4]uint32{1, 3, 5, 7}

type state struct {
	sum   uint32
	count uint32
}

func init() {
	if bootpkg.State == 0x5032494e {
		bootOrder = "imported-init"
	} else {
		bootOrder = "bad-import-init"
	}
	println("P2 PHASE2 INIT")
}

//go:noinline
func nested(a uint32, s *state) uint32 {
	local := a + words[a&3]
	if int32(a) < signedGlobal {
		local ^= uint32(signedGlobal)
	}
	for i := uint32(0); i < 3; i++ {
		local = (local << 1) ^ i
	}
	s.sum += local
	s.count++
	return local
}

func main() {
	var s state
	x := nested(0x80000000, &s)
	if bootOrder == "imported-init" && x == s.sum && s.count == 1 {
		println("READY P2GO")
	} else {
		println("P2 PHASE2 CHECK FAIL")
	}
	for {
	}
}
