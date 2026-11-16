//go:build p2 && !scheduler.cores

package machine

func p2GPIOWrite(pin, value uint32, configure bool) {
	if configure {
		pinDirection(pin, value)
	} else {
		pinSet(pin, value)
	}
}
