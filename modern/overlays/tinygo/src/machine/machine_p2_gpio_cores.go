//go:build p2 && scheduler.cores

package machine

import "sync"

type p2GPIOCommand struct {
	pin       uint32
	value     uint32
	configure bool
}

var (
	p2GPIOOnce      sync.Once
	p2GPIOMutex     sync.Mutex
	p2GPIORequests  chan p2GPIOCommand
	p2GPIOCompleted chan struct{}
)

func p2GPIOExecute(command p2GPIOCommand) {
	if command.configure {
		pinDirection(command.pin, command.value)
	} else {
		pinSet(command.pin, command.value)
	}
}

func p2GPIOStart() {
	p2GPIORequests = make(chan p2GPIOCommand)
	p2GPIOCompleted = make(chan struct{})
	go func() {
		AssignCore(0)
		for command := range p2GPIORequests {
			p2GPIOExecute(command)
			p2GPIOCompleted <- struct{}{}
		}
	}()
}

func p2GPIOWrite(pin, value uint32, configure bool) {
	command := p2GPIOCommand{pin, value, configure}
	if CogID() == 0 {
		p2GPIOExecute(command)
		return
	}
	p2GPIOOnce.Do(p2GPIOStart)
	p2GPIOMutex.Lock()
	p2GPIORequests <- command
	<-p2GPIOCompleted
	p2GPIOMutex.Unlock()
}
