//go:build p2

.section .text.tinygo_swapTaskP2
.global tinygo_swapTaskP2
.global tinygo_swapTask
tinygo_swapTaskP2:
tinygo_swapTask:
	setq #29
	wrlong r0, ptra++
	wrlong ptra, r1
	mov ptra, r0
	tjz r2, #.Lp2_restore
	mov r31, #0
	wrlong r31, r2
.Lp2_restore:
	sub ptra, #120
	setq #29
	rdlong r0, ptra
	reta

.section .text.tinygo_startTask
.global tinygo_startTask
tinygo_startTask:
	mov r0, r5
	calla r4
	calla #\tinygo_task_exit
.Lp2_task_done:
	jmp #.Lp2_task_done

