//go:build p2 && scheduler.cores

package machine

import (
	"errors"
	"runtime/interrupt"
	"sync"
	_ "unsafe"
)

// PSRAMSize is the capacity of the P2-EC32MB's four parallel 8 MiB devices.
const PSRAMSize = 32 * 1024 * 1024

var (
	ErrPSRAMBounds = errors.New("machine: PSRAM access outside 32 MiB")
	ErrPSRAMID     = errors.New("machine: PSRAM chip identification failed")
	ErrPSRAMTiming = errors.New("machine: PSRAM chip-select timing exceeded")
)

type psramRequest struct {
	data  []byte
	off   uint32
	write bool
}

type psramResponse struct {
	count int
	err   error
}

// psramDevice stripes four adjacent bytes over the four quad buses.
// Ordinary Go pointers and the heap remain in P2 hub RAM.
type psramDevice struct {
	once     sync.Once
	mu       sync.Mutex
	requests chan psramRequest
	complete chan psramResponse
	ids      [4][8]byte
	maxTicks uint32
}

// PSRAM uses P40..57 on P2-EC32MB. Its service goroutine shares cog 0 with other
// tasks and owns these pins until reset. Configure or the first access starts it.
var PSRAM = &psramDevice{}

//export p2_psram_init
func psramInit(ids *uint32)

//export p2_psram_read_word
func psramReadWord(address uint32) uint64

//export p2_psram_write_word
func psramWriteWord(address, word uint32) uint32

func (p *psramDevice) start() {
	p.requests = make(chan psramRequest)
	p.complete = make(chan psramResponse)
	go p.serve()
}

func (p *psramDevice) serve() {
	AssignCore(0)
	var ids [8]uint32
	psramInit(&ids[0])
	var initError error
	for bank := range p.ids {
		for i, value := range ids {
			p.ids[bank][i] = byte(value >> (bank * 8))
		}
		if p.ids[bank][0] != 0x0d || p.ids[bank][1] != 0x5d {
			initError = ErrPSRAMID
		}
	}
	for request := range p.requests {
		if initError != nil {
			p.complete <- psramResponse{err: initError}
			continue
		}
		count, err := p.transfer(request)
		p.complete <- psramResponse{count: count, err: err}
	}
}

func (p *psramDevice) recordTicks(ticks uint32) error {
	if ticks > p.maxTicks {
		p.maxTicks = ticks
	}
	// APS6404L rev 2.3 section 14.6 limits standard-grade tCEM to 8 us.
	// The counter includes instructions outside CE, so this is an upper bound.
	if ticks >= CPUFrequency()/125000 {
		return ErrPSRAMTiming
	}
	return nil
}

func (p *psramDevice) transfer(request psramRequest) (int, error) {
	for index := 0; index < len(request.data); {
		offset := request.off + uint32(index)
		within := offset & 3
		count := 4 - int(within)
		if count > len(request.data)-index {
			count = len(request.data) - index
		}
		var value uint32
		if !request.write || within != 0 || count != 4 {
			state := interrupt.Disable()
			result := psramReadWord(offset >> 2)
			interrupt.Restore(state)
			if err := p.recordTicks(uint32(result >> 32)); err != nil {
				return index, err
			}
			value = uint32(result)
		}
		for i := 0; i < count; i++ {
			shift := (within + uint32(i)) * 8
			if request.write {
				value = (value &^ (0xff << shift)) | uint32(request.data[index+i])<<shift
			} else {
				request.data[index+i] = byte(value >> shift)
			}
		}
		if request.write {
			state := interrupt.Disable()
			ticks := psramWriteWord(offset>>2, value)
			interrupt.Restore(state)
			if err := p.recordTicks(ticks); err != nil {
				// Exclude the current word because its validity is unknown.
				return index, err
			}
		}
		index += count
	}
	return len(request.data), nil
}

func (p *psramDevice) access(buffer []byte, offset int64, write bool) (int, error) {
	if offset < 0 || offset > PSRAMSize || int64(len(buffer)) > PSRAMSize-offset {
		return 0, ErrPSRAMBounds
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	p.once.Do(p.start)
	p.requests <- psramRequest{data: buffer, off: uint32(offset), write: write}
	response := <-p.complete
	return response.count, response.err
}

func (p *psramDevice) Configure() error {
	_, err := p.access(nil, 0, false)
	return err
}

// ReadAt copies external memory into a hub-RAM byte slice.
func (p *psramDevice) ReadAt(buffer []byte, offset int64) (int, error) {
	return p.access(buffer, offset, false)
}

// WriteAt copies a hub-RAM byte slice to external memory. Unaligned endpoints
// use a locked read-modify-write, preserving bytes outside the requested span.
func (p *psramDevice) WriteAt(buffer []byte, offset int64) (int, error) {
	return p.access(buffer, offset, true)
}

func (p *psramDevice) Size() int64 { return PSRAMSize }

// IDs returns manufacturer, known-good-die, and extended ID bytes for all banks.
func (p *psramDevice) IDs() ([4][8]byte, error) {
	err := p.Configure()
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.ids, err
}

// MaxTransactionCycles is a measured upper bound on the longest completed
// transaction, including some instructions outside the active CE interval.
func (p *psramDevice) MaxTransactionCycles() uint32 {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.maxTicks
}
