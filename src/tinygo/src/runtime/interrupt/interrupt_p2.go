//go:build p2
// +build p2

// P2 uses a hardware lock for TinyGo's critical-section API. Phase 2 runs one
// cog with scheduler=none; recursive use from that cog is tracked so nested
// Disable/Restore pairs do not deadlock. This is intentionally not a no-op.
package interrupt

type State uintptr

//go:linkname p2_lock_acquire p2_lock_acquire
func p2_lock_acquire()
//go:linkname p2_lock_release p2_lock_release
func p2_lock_release()

var p2CriticalDepth uintptr

func Disable() State {
	previous := p2CriticalDepth
	if previous == 0 {
		p2_lock_acquire()
	}
	p2CriticalDepth = previous + 1
	return State(previous)
}

func Restore(state State) {
	if p2CriticalDepth == 0 || uintptr(state)+1 != p2CriticalDepth {
		panic("runtime/interrupt: unbalanced Restore")
	}
	p2CriticalDepth--
	if p2CriticalDepth == 0 {
		p2_lock_release()
	}
}
