// Package bootpkg supplies observable imported-package initialization.
package bootpkg

// State is initialized before init and read by the main package at boot.
var State = uint32(0x5032494e)

func init() {
	println("P2 PHASE2 IMPORT INIT")
}
