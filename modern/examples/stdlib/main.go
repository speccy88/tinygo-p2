package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"math/bits"
	"sort"
	"strings"
	"time"
	_ "unsafe"
)

//export raw_p2_uart_getc
func uartGet() byte

func nonce() uint32 {
	var value uint32
	for range 8 {
		c := uartGet()
		if c >= 'a' && c <= 'f' {
			c = c - 'a' + 10
		} else if c >= '0' && c <= '9' {
			c -= '0'
		} else {
			panic("bad nonce")
		}
		value = value<<4 | uint32(c)
	}
	if uartGet() != '\r' {
		panic("bad nonce terminator")
	}
	return value
}

type message struct {
	Seed    uint32  `json:"seed"`
	Label   string  `json:"label"`
	Values  []int32 `json:"values"`
	Enabled bool    `json:"enabled,omitempty"`
	Ratio   float64 `json:"ratio"`
}

func main() {
	println("READY P2STDLIB1")
	seed := nonce()
	println("BEGIN", seed)
	wide := uint64(seed)<<32 | uint64(seed^0xa5a5a5a5)
	formatted := fmt.Sprintf("p2:%08x:%d:%d", seed, int32(seed), wide)
	println("FMT", formatted)
	source := message{
		Seed: seed, Label: formatted + "\"\\\n",
		Values:  []int32{int32(seed), int32(^seed), -17},
		Enabled: seed&1 != 0, Ratio: float64(seed&255) / 16,
	}
	encoded, err := json.Marshal(source)
	if err != nil {
		panic(err)
	}
	var decoded message
	if err := json.Unmarshal(encoded, &decoded); err != nil {
		panic(err)
	}
	println("JSON", string(encoded))
	if decoded.Seed != source.Seed || decoded.Label != source.Label || decoded.Enabled != source.Enabled ||
		decoded.Ratio != source.Ratio || len(decoded.Values) != len(source.Values) {
		println("FAIL JSON META", decoded.Seed, source.Seed, decoded.Label == source.Label,
			decoded.Enabled, source.Enabled, math.Float64bits(decoded.Ratio), math.Float64bits(source.Ratio),
			len(decoded.Values), len(source.Values))
		panic("JSON roundtrip metadata mismatch")
	}
	for i, value := range decoded.Values {
		if value != source.Values[i] {
			panic("JSON roundtrip slice mismatch")
		}
	}
	parts := strings.Split("z:go:p2:a", ":")
	parts = append(parts, fmt.Sprintf("%08x", seed))
	sort.Strings(parts)
	text := strings.ReplaceAll(strings.ToUpper(strings.Join(parts, "/")), "GO", "TINYGO")
	println("STR", text)
	values := []int{int(seed & 0xffff), -9, int(seed >> 16), 0, 42}
	sort.Ints(values)
	println("SORT", values[0], values[1], values[2], values[3], values[4])
	var packed [20]byte
	binary.LittleEndian.PutUint32(packed[0:4], seed)
	binary.BigEndian.PutUint64(packed[4:12], wide)
	binary.LittleEndian.PutUint64(packed[12:20], wide^0x0123456789abcdef)
	if binary.LittleEndian.Uint32(packed[0:4]) != seed || binary.BigEndian.Uint64(packed[4:12]) != wide ||
		binary.LittleEndian.Uint64(packed[12:20]) != wide^0x0123456789abcdef {
		panic("binary endian roundtrip mismatch")
	}
	println("BIN", hex.EncodeToString(packed[:]))
	digest := sha256.Sum256(packed[:])
	println("SHA256", hex.EncodeToString(digest[:]))
	println("BITS", bits.RotateLeft32(seed, 13), bits.OnesCount32(seed), bits.LeadingZeros32(seed), bits.TrailingZeros32(seed))
	println("DONE P2STDLIB1", seed)
	for {
		time.Sleep(time.Second)
	}
}
