package main

// challengeState is deliberately passed by reference: the P2 backend only
// supports one scalar return register, while this small state stays in Go.
type challengeState struct {
	sum   uint32
	count uint32
	fold  uint32
}

// Nonzero mutable application globals. They make response/state progression
// depend on prior valid challenges, rather than only on an input expression.
var challengeSeed uint32 = 0x91e10da5
var signedBias int32 = -19
var challengeWords = [4]uint32{0x13579bdf, 0x2468ace0, 0xf00dcafe, 0x10203040}

//go:noinline
func foldWords(x uint32, st *challengeState) uint32 {
	v := st.fold ^ challengeSeed
	for i := uint32(0); i < 4; i++ {
		v = (v << 3) | (v >> 29)
		v ^= challengeWords[(x+i)&3]
	}
	return v
}

// mixChallenge intentionally retains local across the non-inlined foldWords
// call. Its branch and bounded iteration count are all host-controlled.
//go:noinline
func mixChallenge(a uint32, b uint32, limit uint32, st *challengeState) uint32 {
	local := a + challengeWords[(a^b)&3] // uint32 wrap is protocol semantics.
	fold := foldWords(local, st)
	if int32(a) < signedBias {
		local ^= uint32(signedBias)
	} else if a > uint32(signedBias) { // intentional signed/unsigned contrast.
		local += b
	} else {
		local ^= 0xa5a5a5a5
	}
	for i := uint32(0); i < (limit&15)+1; i++ {
		local = ((local << 5) | (local >> 27)) ^ fold ^ i
		fold += challengeWords[(i+st.count)&3]
	}
	st.sum += local
	st.count++
	st.fold = fold ^ local
	challengeSeed += local + b + limit
	return (local ^ st.sum ^ st.fold) ^ 1
}

func hexDigit(c byte) uint32 {
	if c >= '0' && c <= '9' {
		return uint32(c - '0')
	}
	if c >= 'a' && c <= 'f' {
		return uint32(c-'a') + 10
	}
	if c >= 'A' && c <= 'F' {
		return uint32(c-'A') + 10
	}
	return 0xffffffff
}

// parseHex8 never returns a tuple: bad is returned through its pointer.
func parseHex8(buf *[64]byte, offset uint32, bad *uint32) uint32 {
	v := uint32(0)
	*bad = 0
	for i := uint32(0); i < 8; i++ {
		d := hexDigit(buf[offset+i])
		if d == 0xffffffff {
			*bad = 1
			return 0
		}
		v = (v << 4) | d
	}
	return v
}

func processChallenge(buf *[64]byte, length uint32, st *challengeState, out *[4]uint32, bad *uint32) {
	*bad = 0
	if length != 37 || buf[0] != 'C' || buf[1] != ' ' || buf[10] != ' ' || buf[19] != ' ' || buf[28] != ' ' {
		*bad = 1
		return
	}
	id := parseHex8(buf, 2, bad)
	if *bad != 0 {
		return
	}
	a := parseHex8(buf, 11, bad)
	if *bad != 0 {
		return
	}
	b := parseHex8(buf, 20, bad)
	if *bad != 0 {
		return
	}
	limit := parseHex8(buf, 29, bad)
	if *bad != 0 {
		return
	}
	out[0] = id
	out[1] = mixChallenge(a, b, limit, st)
	out[2] = st.sum
	out[3] = st.count
}
