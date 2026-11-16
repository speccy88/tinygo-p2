//go:build p2 && !(gc.conservative || gc.precise)

package runtime

func initP2GC() {}
