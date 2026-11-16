//go:build p2

// P2 ABI: r0/r1/r2 are destination/source-or-byte/length, r31 is the result.
// Preserve r0-r29 and PTRA; scratch $000-$07f, PA/PB/PTRB and r30/r31 are volatile.

// The GC interrupt preserves those volatile registers without using scratch.
// Keep original pointer arguments live and never borrow the stack or hub FIFO.

// See P2 silicon documentation, Fast Block Moves and Interrupts:
// https://p2docs.github.io/mirror/p2silicon.html

.section .text.memcpy
.global memcpy
memcpy:
	mov pa, r0
	mov ptrb, r1
	mov pb, r2
	tjz pb, #.Lp2_copy_done
	mov r30, pa
	xor r30, ptrb
	and r30, #3
	tjnz r30, #.Lp2_copy_bytes
.Lp2_copy_align:
	test pa, #3 wz
	if_z jmp #.Lp2_copy_blocks
	rdbyte r31, ptrb++
	wrbyte r31, pa
	add pa, #1
	djnz pb, #.Lp2_copy_align
	jmp #.Lp2_copy_done
.Lp2_copy_blocks:
	cmp pb, ##512 wc
	if_c jmp #.Lp2_copy_longs
	setq #127
	rdlong $0, ptrb++
	setq #127
	wrlong $0, pa
	add pa, ##512
	sub pb, ##512
	jmp #.Lp2_copy_blocks
.Lp2_copy_longs:
	mov r30, pb
	shr r30, #2
	tjz r30, #.Lp2_copy_bytes
	sub r30, #1
	setq r30
	rdlong $0, ptrb++
	setq r30
	wrlong $0, pa
	add r30, #1
	shl r30, #2
	add pa, r30
	and pb, #3
.Lp2_copy_bytes:
	tjz pb, #.Lp2_copy_done
.Lp2_copy_byte:
	rdbyte r31, ptrb++
	wrbyte r31, pa
	add pa, #1
	djnz pb, #.Lp2_copy_byte
.Lp2_copy_done:
	mov r31, r0
	reta

.section .text.memmove
.global memmove
memmove:
	cmp r0, r1 wcz
	if_c jmp #memcpy
	if_z jmp #.Lp2_move_done
	tjz r2, #.Lp2_move_done
	mov pa, r0
	add pa, r2
	mov ptrb, r1
	add ptrb, r2
	mov pb, r2
	mov r30, pa
	xor r30, ptrb
	and r30, #3
	tjnz r30, #.Lp2_move_bytes
.Lp2_move_align:
	test pa, #3 wz
	if_z jmp #.Lp2_move_blocks
	sub pa, #1
	rdbyte r31, --ptrb
	wrbyte r31, pa
	djnz pb, #.Lp2_move_align
	jmp #.Lp2_move_done
.Lp2_move_blocks:
	cmp pb, ##512 wc
	if_c jmp #.Lp2_move_longs
	setq #127
	rdlong $0, --ptrb
	sub pa, ##512
	setq #127
	wrlong $0, pa
	sub pb, ##512
	jmp #.Lp2_move_blocks
.Lp2_move_longs:
	mov r30, pb
	shr r30, #2
	tjz r30, #.Lp2_move_bytes
	sub r30, #1
	setq r30
	rdlong $0, --ptrb
	add r30, #1
	shl r30, #2
	sub pa, r30
	shr r30, #2
	sub r30, #1
	setq r30
	wrlong $0, pa
	and pb, #3
.Lp2_move_bytes:
	tjz pb, #.Lp2_move_done
.Lp2_move_byte:
	sub pa, #1
	rdbyte r31, --ptrb
	wrbyte r31, pa
	djnz pb, #.Lp2_move_byte
.Lp2_move_done:
	mov r31, r0
	reta

.section .text.memset
.global memset
memset:
	mov ptrb, r0
	mov pb, r2
	tjz pb, #.Lp2_set_done
	mov r31, r1
	and r31, #255
.Lp2_set_align:
	test ptrb, #3 wz
	if_z jmp #.Lp2_set_pattern
	wrbyte r31, ptrb++
	djnz pb, #.Lp2_set_align
	jmp #.Lp2_set_done
.Lp2_set_pattern:
	tjz r31, #.Lp2_zero_blocks
	mov r30, r31
	shl r30, #8
	or r31, r30
	mov r30, r31
	shl r30, #16
	or r31, r30
.Lp2_set_longs:
	cmp pb, #4 wc
	if_c jmp #.Lp2_set_bytes
	wrlong r31, ptrb++
	sub pb, #4
	jmp #.Lp2_set_longs
.Lp2_zero_blocks:
	cmp pb, ##512 wc
	if_c jmp #.Lp2_zero_longs
	setq #127
	wrlong #0, ptrb++
	sub pb, ##512
	jmp #.Lp2_zero_blocks
.Lp2_zero_longs:
	mov r30, pb
	shr r30, #2
	tjz r30, #.Lp2_set_bytes
	sub r30, #1
	setq r30
	wrlong #0, ptrb++
	and pb, #3
.Lp2_set_bytes:
	tjz pb, #.Lp2_set_done
.Lp2_set_byte:
	wrbyte r31, ptrb++
	djnz pb, #.Lp2_set_byte
.Lp2_set_done:
	mov r31, r0
	reta
