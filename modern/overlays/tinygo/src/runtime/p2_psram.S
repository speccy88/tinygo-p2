//go:build p2

// P2-EC32MB parallel quad transfers preserve R0..R29. The caller stalls IRQs.
// Timing follows APS6404L rev 2.3 sections 11 and 14.6: https://www.pjrc.com/store/APS6404L_3SQR.pdf

.macro p2_psram_address_nibble index
	getnib pa, r0, #\index
	setnib pa, pa, #1
	setbyte pa, pa, #1
	shl pa, #8
	andn outb, r30
	or outb, pa
	outh #56
	outl #56
.endm

.macro p2_psram_prefix hi, lo
	mov r30, ##0x00ffff00
	outl #56
	or dirb, r30
	getct ptrb
	outl #57
	andn outb, r30
	or outb, ##\hi
	outh #56
	outl #56
	andn outb, r30
	or outb, ##\lo
	outh #56
	outl #56
	p2_psram_address_nibble 5
	p2_psram_address_nibble 4
	p2_psram_address_nibble 3
	p2_psram_address_nibble 2
	p2_psram_address_nibble 1
	p2_psram_address_nibble 0
.endm

.section .text.p2_psram_read_word
.global p2_psram_read_word
// uint64: low word = memory data, high word = elapsed CT cycles.
p2_psram_read_word:
	p2_psram_prefix 0x00eeee00, 0x00bbbb00
	andn dirb, r30
	// Six dummy clocks. Data changes on falling edges.
	outh #56
	outl #56
	outh #56
	outl #56
	outh #56
	outl #56
	outh #56
	outl #56
	outh #56
	outl #56
	outh #56
	outl #56
	// Allow GPIO output/input pipelines and PSRAM tACLK to settle.
	waitx #8
	mov pb, inb
	outh #56
	outl #56
	waitx #8
	mov pa, inb
	outh #56
	outl #56
	nop
	outh #57
	// Decode four packed high/low nibble pairs after terminating refresh hold.
	getnib r31, pb, #2
	setnib r30, r31, #1
	getnib r31, pa, #2
	setnib r30, r31, #0
	getnib r31, pb, #3
	setnib r30, r31, #3
	getnib r31, pa, #3
	setnib r30, r31, #2
	getnib r31, pb, #4
	setnib r30, r31, #5
	getnib r31, pa, #4
	setnib r30, r31, #4
	getnib r31, pb, #5
	setnib r30, r31, #7
	getnib r31, pa, #5
	setnib r30, r31, #6
	getct r31
	sub r31, ptrb
	reta

.section .text.p2_psram_write_word
.global p2_psram_write_word
// R0 = physical address (logical byte address/4), R1 = packed data.
// Returns elapsed cycles, including packing, conservatively above actual tCEM.
p2_psram_write_word:
	// Pack high nibbles in PB and low nibbles in R31 before CE goes low.
	getnib pb, r1, #1
	getnib pa, r1, #3
	setnib pb, pa, #1
	getnib pa, r1, #5
	setnib pb, pa, #2
	getnib pa, r1, #7
	setnib pb, pa, #3
	shl pb, #8
	getnib r31, r1, #0
	getnib pa, r1, #2
	setnib r31, pa, #1
	getnib pa, r1, #4
	setnib r31, pa, #2
	getnib pa, r1, #6
	setnib r31, pa, #3
	shl r31, #8
	p2_psram_prefix 0x00333300, 0x00888800
	andn outb, r30
	or outb, pb
	outh #56
	outl #56
	andn outb, r30
	or outb, r31
	outh #56
	outl #56
	outh #57
	getct r31
	sub r31, ptrb
	andn dirb, r30
	reta
