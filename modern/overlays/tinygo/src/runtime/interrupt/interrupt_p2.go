//go:build p2

package interrupt

type State uintptr

var criticalDepth [8]uintptr

//export p2_cog_id
func cogID() uint32

//export p2_irq_stall
func stall()

//export p2_irq_allow
func allow()

func Disable() State {
	stall()
	core := cogID()
	previous := criticalDepth[core]
	criticalDepth[core] = previous + 1
	return State(previous)
}

func Restore(state State) {
	core := cogID()
	if criticalDepth[core] != uintptr(state)+1 {
		panic("runtime/interrupt: unbalanced Restore")
	}
	criticalDepth[core] = uintptr(state)
	if state == 0 {
		allow()
	}
}

func In() bool { return false }
