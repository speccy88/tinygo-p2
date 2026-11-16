//go:build (scheduler.tasks || scheduler.cores) && !p2

package task

import "unsafe"

func (s *state) initializeStack(stack unsafe.Pointer, stackSize uintptr) *calleeSavedRegs {
	s.canaryPtr = (*uintptr)(stack)
	*s.canaryPtr = stackCanary
	return (*calleeSavedRegs)(unsafe.Add(stack, stackSize-unsafe.Sizeof(calleeSavedRegs{})))
}
