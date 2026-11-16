//go:build p2

.section .text.p2_gc_install
.global p2_gc_install
p2_gc_install:
	mov ijmp2, r0
	mov ijmp1, ##p2_gc_irq
	setint1 #14
	allowi
	reta

.section .text.p2_cog_attention
.global p2_cog_attention
p2_cog_attention:
	cogatn r0
	reta

// P2 silicon documentation, Interrupts: ATN is event 14; RETI1 restores C/Z/PC.
.section .text.p2_gc_irq
.global p2_gc_irq
p2_gc_irq:
	setq #31
	wrlong r0, ijmp2
	mov r0, ijmp2
	add r0, #128
	wrlong ptra, r0
	add r0, #4
	wrlong ptrb, r0
	add r0, #4
	wrlong pa, r0
	add r0, #4
	wrlong pb, r0
	add r0, #4
	mov r31, #1
	wrlong r31, r0
	add r0, #4
.Lp2_gc_park:
	rdlong r31, r0
	tjnz r31, #.Lp2_gc_resume
	waitx #128
	jmp #.Lp2_gc_park
.Lp2_gc_resume:
	sub r0, #4
	mov r31, #0
	wrlong r31, r0
	sub r0, #4
	rdlong pb, r0
	sub r0, #4
	rdlong pa, r0
	sub r0, #4
	rdlong ptrb, r0
	setq #31
	rdlong r0, ijmp2
	reti1

.section .text.tinygo_scanCurrentStack
.global tinygo_scanCurrentStack
tinygo_scanCurrentStack:
	setq #29
	wrlong r0, ptra++
	mov r0, ptra
	calla #\tinygo_scanstack
	sub ptra, #120
	setq #29
	rdlong r0, ptra
	reta

