//go:build p2

.section .text.p2_cog_id
.global p2_cog_id
p2_cog_id:
	cogid r31
	reta

.section .text.p2_counter
.global p2_counter
p2_counter:
	getct r31 wc
	getct r30
	reta

.section .text.p2_stack_pointer
.global p2_stack_pointer
p2_stack_pointer:
	mov r31, ptra
	reta

.section .text.p2_wait
.global p2_wait
p2_wait:
	waitx #128
	reta

.section .text.p2_lock_new
.global p2_lock_new
p2_lock_new:
	locknew r31 wc
	if_c neg r31, #1
	reta

.section .text.p2_lock_acquire_id
.global p2_lock_acquire_id
p2_lock_acquire_id:
	locktry r0 wc
	if_nc jmp #p2_lock_acquire_id
	reta

.section .text.p2_lock_release_id
.global p2_lock_release_id
p2_lock_release_id:
	lockrel r0
	reta

.section .text.p2_irq_stall
.global p2_irq_stall
p2_irq_stall:
	stalli
	reta

.section .text.p2_irq_allow
.global p2_irq_allow
p2_irq_allow:
	allowi
	reta


.section .text.p2_pin_dir
.global p2_pin_dir
p2_pin_dir:
 dirl r0
 wrpin #0, r0
 cmp r1, #0 wz
 if_nz dirh r0
 reta

.section .text.p2_pin_set
.global p2_pin_set
p2_pin_set:
 cmp r1, #0 wz
 if_z outl r0
 if_nz outh r0
 reta

.section .text.p2_pin_get
.global p2_pin_get
p2_pin_get:
 testp r0 wc
 wrc r31
 reta
