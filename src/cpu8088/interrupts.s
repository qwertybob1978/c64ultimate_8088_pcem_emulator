.setcpu "6502"

.include "cpu8088/state.inc"

.import cpu8088_state
.import cpu8088_halted
.import cpu8088_push_u16
.import cpu8088_pop_u16
.import cpu8088_segment_offset_physical
.import cpu8088_mem_read_u8
.importzp cpu8088_segment
.importzp cpu8088_offset

.export cpu8088_interrupt
.export cpu8088_iret
.export cpu8088_request_irq
.export cpu8088_request_nmi
.export cpu8088_service_pending_interrupt
.export cpu8088_irq_vector
.export cpu8088_irq_pending
.export cpu8088_nmi_pending
.export cpu8088_interrupt_shadow
.export cpu8088_irq6_serviced
.export cpu8088_interrupt_stage
.export cpu8088_stack_stage
.export interrupt_last_iret_ip
.export interrupt_last_iret_cs
.export interrupt_last_iret_stage
.export interrupt_vector

.macro long_bcs target
    bcc :+
    jmp target
:
.endmacro

.segment "BSS"
interrupt_vector: .res 1
interrupt_ip:     .res 2
interrupt_cs:     .res 2
interrupt_flags:  .res 2
cpu8088_irq_vector:       .res 1
cpu8088_irq_pending:      .res 1
cpu8088_nmi_pending:      .res 1
cpu8088_interrupt_shadow: .res 1
cpu8088_irq6_serviced:    .res 1
cpu8088_interrupt_stage:  .res 1
cpu8088_stack_stage:       .res 1
interrupt_last_iret_ip:    .res 2
interrupt_last_iret_cs:    .res 2
interrupt_last_iret_stage: .res 1

.segment "CODE"

cpu8088_request_irq:
    sta cpu8088_irq_vector
    lda #$01
    sta cpu8088_irq_pending
    rts

cpu8088_request_nmi:
    lda #$01
    sta cpu8088_nmi_pending
    rts

; Poll at an instruction boundary. Carry means memory failure; otherwise A is
; zero when nothing was delivered and one when interrupt entry completed.
cpu8088_service_pending_interrupt:
    lda cpu8088_nmi_pending
    beq @check_shadow
    lda #$00
    sta cpu8088_nmi_pending
    lda #$02
    bne @service
@check_shadow:
    lda cpu8088_interrupt_shadow
    beq @check_irq
    dec cpu8088_interrupt_shadow
    lda #$00
    clc
    rts
@check_irq:
    lda cpu8088_irq_pending
    beq @none
    lda cpu8088_state+CPU_SP
    ora cpu8088_state+CPU_SP+1
    beq @none
    lda cpu8088_state+CPU_FLAGS+1
    and #$02
    beq @none
    lda #$00
    sta cpu8088_irq_pending
    lda cpu8088_irq_vector
@service:
    jsr cpu8088_interrupt
    bcs @service_failed
    lda interrupt_vector
    cmp #$0E
    bne :+
    inc cpu8088_irq6_serviced
:
    lda #$00
    sta cpu8088_halted
    lda #$01
    clc
@service_failed:
    rts
@none:
    lda #$00
    clc
    rts

; Enter an 8088 real-mode interrupt. A is the vector number. The return frame
; is FLAGS, CS, IP in push order, leaving IP at SS:SP. Carry reports REU error.
cpu8088_interrupt:
    sta interrupt_vector
    lda #$01
    sta cpu8088_interrupt_stage
    lda cpu8088_state+CPU_FLAGS
    ldx cpu8088_state+CPU_FLAGS+1
    txa
    ora #$F0                    ; 8088 exposes high FLAGS bits as ones on frame
    tax
    lda cpu8088_state+CPU_FLAGS
    jsr cpu8088_push_u16
    long_bcs @failed
    lda #$02
    sta cpu8088_interrupt_stage
    lda cpu8088_state+CPU_CS
    ldx cpu8088_state+CPU_CS+1
    jsr cpu8088_push_u16
    long_bcs @failed
    lda #$03
    sta cpu8088_interrupt_stage
    lda cpu8088_state+CPU_IP
    ldx cpu8088_state+CPU_IP+1
    jsr cpu8088_push_u16
    long_bcs @failed

    lda cpu8088_state+CPU_FLAGS+1
    and #$FC                    ; clear TF and IF
    sta cpu8088_state+CPU_FLAGS+1

    lda #$00
    sta cpu8088_segment
    sta cpu8088_segment+1
    sta cpu8088_offset+1
    lda interrupt_vector
    asl a
    rol cpu8088_offset+1
    asl a
    rol cpu8088_offset+1
    sta cpu8088_offset
    jsr cpu8088_segment_offset_physical
    jsr interrupt_read_vector_byte
    bcs @failed
    pha
    lda #$04
    sta cpu8088_interrupt_stage
    pla
    sta interrupt_ip
    jsr interrupt_read_vector_byte
    bcs @failed
    sta interrupt_ip+1
    jsr interrupt_read_vector_byte
    bcs @failed
    sta interrupt_cs
    jsr cpu8088_mem_read_u8
    bcs @failed
    sta interrupt_cs+1

    lda interrupt_cs
    bne @install_vector
    lda interrupt_cs+1
    cmp #$F0
    bne @install_vector
    lda interrupt_ip
    bne @install_vector
    lda interrupt_ip+1
    cmp #$E0
    bne @install_vector
    lda interrupt_vector
    cmp #$08
    bcc @install_vector
    cmp #$20
    bcs @install_vector
    sec
    sbc #$08
    asl a
    tax
    lda genxt_vector_offsets,x
    sta interrupt_ip
    lda genxt_vector_offsets+1,x
    sta interrupt_ip+1

@install_vector:
    lda interrupt_ip
    sta cpu8088_state+CPU_IP
    lda interrupt_ip+1
    sta cpu8088_state+CPU_IP+1
    lda interrupt_cs
    sta cpu8088_state+CPU_CS
    lda interrupt_cs+1
    sta cpu8088_state+CPU_CS+1
    clc
@failed:
    rts

; Return from a real-mode interrupt frame, restoring IP, CS, then FLAGS.
cpu8088_iret:
    jsr cpu8088_pop_u16
    bcs @failed
    sta interrupt_ip
    stx interrupt_ip+1
    sta interrupt_last_iret_ip
    stx interrupt_last_iret_ip+1
    lda #$01
    sta interrupt_last_iret_stage
    jsr cpu8088_pop_u16
    bcs @failed
    sta interrupt_cs
    stx interrupt_cs+1
    sta interrupt_last_iret_cs
    stx interrupt_last_iret_cs+1
    lda #$02
    sta interrupt_last_iret_stage
    jsr cpu8088_pop_u16
    bcs @failed
    lda #$03
    sta interrupt_last_iret_stage
    ora #$02                    ; reserved bit is architecturally set
    sta interrupt_flags
    txa
    and #$0F
    sta interrupt_flags+1
    lda interrupt_ip
    sta cpu8088_state+CPU_IP
    lda interrupt_ip+1
    sta cpu8088_state+CPU_IP+1
    lda interrupt_cs
    sta cpu8088_state+CPU_CS
    lda interrupt_cs+1
    sta cpu8088_state+CPU_CS+1
    lda interrupt_flags
    sta cpu8088_state+CPU_FLAGS
    lda interrupt_flags+1
    sta cpu8088_state+CPU_FLAGS+1
    clc
@failed:
    rts

interrupt_read_vector_byte:
    jsr cpu8088_mem_read_u8
    bcs @read_failed
    pha
    inc cpu8088_offset
    bne :+
    inc cpu8088_offset+1
:
    jsr cpu8088_segment_offset_physical
    pla
    clc
@read_failed:
    rts

.segment "RODATA"
genxt_vector_offsets:
    .word $FEA5,$E987,$FF23,$FF23,$FF23,$FF23,$EF57,$FF23
    .word $F065,$F84D,$F841,$EC59,$E739,$F859,$E82E,$EFD2
    .word $FF23,$E6F2,$FE6E,$FF53,$FF53,$F0A4,$EFC7,$0000
