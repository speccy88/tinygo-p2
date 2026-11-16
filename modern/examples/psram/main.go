package main

import (
	"machine"
	"time"
	_ "unsafe"
)

//export raw_p2_uart_getc
func uartGet() byte

func pattern(seed, address uint32) byte {
	x := seed ^ (address * 0x9e3779b9)
	x ^= x >> 16
	x *= 0x7feb352d
	x ^= x >> 15
	return byte(x)
}

func main() {
	println("READY P2PSRAM1")
	var seed uint32
	for range 8 {
		c := uartGet()
		if c >= 'a' && c <= 'f' {
			c = c - 'a' + 10
		} else if c >= '0' && c <= '9' {
			c -= '0'
		} else {
			panic("bad nonce")
		}
		seed = seed<<4 | uint32(c)
	}
	if uartGet() != '\r' {
		panic("bad nonce terminator")
	}
	println("BEGIN", seed)
	ids, err := machine.PSRAM.IDs()
	for bank, id := range ids {
		println("ID", bank, id[0], id[1], id[2], id[3], id[4], id[5], id[6], id[7])
	}
	if err != nil {
		panic(err)
	}
	var write, read [259]byte
	// Exercise interleaving, unaligned endpoints, physical page boundaries,
	// every high address bit, and the very last bytes of all four devices.
	addresses := []uint32{0, 3, 63, 4093, 8191, 65533, 1048573, 8388605, 16777213, 33554173}
	var checksum uint32
	for _, address := range addresses {
		for index := range write {
			write[index] = pattern(seed, address+uint32(index))
		}
		if count, err := machine.PSRAM.WriteAt(write[:], int64(address)); count != len(write) || err != nil {
			println("WRITE", address, count)
			panic(err)
		}
	}
	// Read only after all writes, so a missing high address bit cannot pass by
	// merely reading back the most recent value from an aliased location.
	time.Sleep(10 * time.Millisecond)
	for _, address := range addresses {
		for index := range write {
			write[index] = pattern(seed, address+uint32(index))
			read[index] = ^write[index]
		}
		if count, err := machine.PSRAM.ReadAt(read[:], int64(address)); count != len(read) || err != nil {
			println("READ", address, count)
			panic(err)
		}
		for index, value := range read {
			if value != write[index] {
				println("MISMATCH", address+uint32(index), value, write[index])
				panic("PSRAM mismatch")
			}
			checksum = (checksum << 5) | (checksum >> 27)
			checksum ^= uint32(value)
		}
	}
	var guard [16]byte
	for i := range guard {
		guard[i] = 0xc3
	}
	if _, err := machine.PSRAM.WriteAt(guard[:], 1234560); err != nil {
		panic(err)
	}
	if _, err := machine.PSRAM.WriteAt([]byte{0x12, 0x34, 0x56}, 1234565); err != nil {
		panic(err)
	}
	if _, err := machine.PSRAM.ReadAt(guard[:], 1234560); err != nil {
		panic(err)
	}
	for i, value := range guard {
		expected := byte(0xc3)
		if i >= 5 && i < 8 {
			expected = []byte{0x12, 0x34, 0x56}[i-5]
		}
		if value != expected {
			panic("PSRAM unaligned write damaged adjacent bytes")
		}
	}
	if _, err := machine.PSRAM.ReadAt(read[:1], -1); err != machine.ErrPSRAMBounds {
		panic("negative PSRAM offset accepted")
	}
	if _, err := machine.PSRAM.WriteAt(write[:2], machine.PSRAMSize-1); err != machine.ErrPSRAMBounds {
		panic("PSRAM overflow accepted")
	}
	println("PSRAM", len(addresses)*len(write), checksum, machine.PSRAM.MaxTransactionCycles())
	println("DONE P2PSRAM1", seed)
	for {
		time.Sleep(time.Second)
	}
}
