//go:build p2

package machine

import (
	"errors"
	"runtime"
	"sync"
	_ "unsafe"
)

const deviceName = "Propeller 2 P2X8C4M64P"
const UART_TX_PIN = Pin(62)
const UART_RX_PIN = Pin(63)

const (
	PinInput PinMode = iota
	PinOutput
)

func CPUFrequency() uint32 { return 160_000_000 }

//export p2_cog_id
func rawCogID() uint32

func CogID() uint32 { return rawCogID() }

//export p2_pin_dir
func pinDirection(pin, output uint32)

//export p2_pin_set
func pinSet(pin, high uint32)

//export p2_pin_get
func pinGet(pin uint32) uint32

func (p Pin) Configure(config PinConfig) {
	if p >= 64 || config.Mode > PinOutput {
		panic("machine: unsupported P2 pin configuration")
	}
	p2GPIOWrite(uint32(p), uint32(config.Mode), true)
}

func (p Pin) Set(high bool) {
	if p >= 64 {
		panic("machine: invalid P2 pin")
	}
	value := uint32(0)
	if high {
		value = 1
	}
	p2GPIOWrite(uint32(p), value, false)
}

func (p Pin) Get() bool {
	if p >= 64 {
		panic("machine: invalid P2 pin")
	}
	return pinGet(uint32(p)) != 0
}

type UART struct{ rxLock sync.Mutex }

var UART0 = &UART{}
var DefaultUART = UART0

func (uart *UART) Configure(config UARTConfig) error {
	if (config.BaudRate != 0 && config.BaudRate != 115200) ||
		(config.TX != 0 && config.TX != UART_TX_PIN) ||
		(config.RX != 0 && config.RX != UART_RX_PIN) ||
		config.InvertTX || config.InvertRX {
		return errors.New("P2 console supports P62/P63 at 115200 baud")
	}
	return nil
}

func (uart *UART) Write(data []byte) (int, error) {
	serialWrite(data)
	return len(data), nil
}

func (uart *UART) WriteByte(c byte) error {
	serialWriteByte(c)
	return nil
}

//go:linkname serialWrite runtime.p2SerialWrite
func serialWrite(data []byte)

//go:linkname serialWriteByte runtime.p2SerialWriteByte
func serialWriteByte(c byte)

//export raw_p2_uart_buffered
func uartBuffered() int

//export raw_p2_uart_getc
func uartGetc() byte

func (uart *UART) Buffered() int { return uartBuffered() }

func (uart *UART) ReadByte() (byte, error) {
	uart.rxLock.Lock()
	for uartBuffered() == 0 {
		runtime.Gosched()
	}
	c := uartGetc()
	uart.rxLock.Unlock()
	return c, nil
}

func (uart *UART) Read(data []byte) (int, error) {
	if len(data) == 0 || uartBuffered() == 0 {
		return 0, nil
	}
	c, err := uart.ReadByte()
	data[0] = c
	return 1, err
}

func (uart *UART) DTR() bool { return false }
func (uart *UART) RTS() bool { return false }
