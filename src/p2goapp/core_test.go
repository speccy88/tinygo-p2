package main

import "testing"

func reference(a, b, limit uint32, st *challengeState, seed *uint32) uint32 {
	local := a + challengeWords[(a^b)&3]
	fold := st.fold ^ *seed
	for i := uint32(0); i < 4; i++ {
		fold = (fold << 3) | (fold >> 29)
		fold ^= challengeWords[(local+i)&3]
	}
	if int32(a) < signedBias {
		local ^= uint32(signedBias)
	} else if a > uint32(signedBias) {
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
	*seed += local + b + limit
	return local ^ st.sum ^ st.fold
}

func line(id, a, b, n uint32) [64]byte {
	var out [64]byte
	const digits = "0123456789abcdef"
	out[0], out[1] = 'C', ' '
	fields := [4]uint32{id, a, b, n}
	at := [4]uint32{2, 11, 20, 29}
	for f := uint32(0); f < 4; f++ {
		for j := uint32(0); j < 8; j++ {
			out[at[f]+j] = digits[(fields[f]>>(28-j*4))&15]
		}
		if f != 3 {
			out[at[f]+8] = ' '
		}
	}
	return out
}

func TestChallengeAgainstIndependentReference(t *testing.T) {
	vectors := [6][4]uint32{{0, 0, 0, 0}, {1, 0xffffffff, 1, 15}, {2, 0x80000000, 0x7fffffff, 16}, {3, 0x7fffffff, 0xffffffff, 3}, {4, 19, 0xdeadbeef, 31}, {5, 0xffffffff, 0xffffffff, 0xffffffff}}
	challengeSeed = 0x91e10da5
	var got, want challengeState
	seed := uint32(0x91e10da5)
	for _, v := range vectors {
		buf := line(v[0], v[1], v[2], v[3])
		var out [4]uint32
		bad := uint32(0)
		processChallenge(&buf, 37, &got, &out, &bad)
		if bad != 0 {
			t.Fatal("valid input rejected")
		}
		value := reference(v[1], v[2], v[3], &want, &seed)
		if out != [4]uint32{v[0], value, want.sum, want.count} {
			t.Fatalf("%08x: got %#v want %#v", v[0], out, [4]uint32{v[0], value, want.sum, want.count})
		}
	}
}

func TestChallengeRejectsMalformed(t *testing.T) {
	var st challengeState
	var out [4]uint32
	buf := line(1, 2, 3, 4)
	buf[13] = 'z'
	bad := uint32(0)
	processChallenge(&buf, 37, &st, &out, &bad)
	if bad == 0 || st.count != 0 {
		t.Fatalf("malformed input accepted: bad=%d state=%#v", bad, st)
	}
	processChallenge(&buf, 36, &st, &out, &bad)
	if bad == 0 {
		t.Fatal("short input accepted")
	}
}
