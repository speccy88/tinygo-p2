//go:build p2 && !scheduler.cores

package runtime

func initP2Runtime() {}

//export tinygo_runCore
func runP2Core() { abort() }
