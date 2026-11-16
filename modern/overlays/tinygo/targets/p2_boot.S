//go:build p2

// P2 COGINIT uses a hub byte address, then starts the loaded image at cog 0.
// P2 silicon doc, Starting and Stopping Cogs: https://p2docs.github.io/mirror/p2silicon.html

.section .text.__entry,"ax",@progbits
.global __entry
.type __entry,@function
__entry:
	jmp #\0x10
.size __entry, .-__entry

.section .p2.boot,"ax",@progbits
.global __start0
.type __start0,@function
__start0:
	mov r31, ##__start
	coginit #0, r31
.size __start0, .-__start0

.global __start
.type __start,@function
__start:
	setq2 #511
	augs #1
	rdlong $0, #0
	mov pa, ##_stack_bottom
	mov pb, ##p2_primary_entry
	mov r31, ##tinygo_runCore
	cogid r0
	cmp r0, #0 wz
	if_z mov ptra, pa
	if_z mov r31, pb
	jmp r31
.size __start, .-__start

.global __p2_boot_end
__p2_boot_end:
