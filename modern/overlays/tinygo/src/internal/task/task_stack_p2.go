//go:build (scheduler.tasks || scheduler.cores) && p2

package task

import "unsafe"

// The P2 ABI places the return word below R0-R29 on its ascending stack.
type calleeSavedRegs struct {
	pc   uintptr
	regs [30]uintptr
}

func (s *state) initializeStack(stack unsafe.Pointer, stackSize uintptr) *calleeSavedRegs {
	if stackSize < unsafe.Sizeof(calleeSavedRegs{})+unsafe.Sizeof(uintptr(0)) {
		runtimeFatal("P2 goroutine stack too small")
	}
	s.canaryPtr = (*uintptr)(unsafe.Add(stack, stackSize-unsafe.Sizeof(uintptr(0))))
	*s.canaryPtr = stackCanary
	return (*calleeSavedRegs)(stack)
}

func (s *state) archInit(r *calleeSavedRegs, fn uintptr, args unsafe.Pointer) {
	s.sp = uintptr(unsafe.Pointer(r)) + unsafe.Sizeof(*r)
	r.pc = uintptr(unsafe.Pointer(&startTask))
	r.regs[4] = fn
	r.regs[5] = uintptr(args)
}

//go:linkname runtime_systemStackPtr runtime.systemStackPtr
func runtime_systemStackPtr() *uintptr

//export tinygo_swapTaskP2
func swapTaskP2(newStack uintptr, oldStack, clearStack *uintptr)

func (s *state) resume() {
	swapTaskP2(s.sp, runtime_systemStackPtr(), nil)
}

func (s *state) pause() {
	system := runtime_systemStackPtr()
	swapTaskP2(*system, &s.sp, system)
}

func SystemStack() uintptr { return *runtime_systemStackPtr() }

func OnSystemStack() bool { return SystemStack() == 0 }
