.setcpu "6502"

.include "cpu8088/state.inc"

.import cpu8088_state
.import cpu8088_segment_offset_physical
.importzp cpu8088_segment
.importzp cpu8088_offset
.import cpu8088_mem_read_u8
.import cpu8088_mem_write_u8

.export cpu8088_push_u16
.export cpu8088_pop_u16

.segment "BSS"
stack_value: .res 2

.segment "CODE"

; Push A(low)/X(high), or pop into A(low)/X(high). Carry reports DMA failure.
cpu8088_push_u16:
    sta stack_value
    stx stack_value+1
    sec
    lda cpu8088_state+CPU_SP
    sbc #$02
    sta cpu8088_state+CPU_SP
    lda cpu8088_state+CPU_SP+1
    sbc #$00
    sta cpu8088_state+CPU_SP+1
    jsr stack_address
    lda stack_value
    jsr cpu8088_mem_write_u8
    bcs stack_failed
    jsr stack_next_byte
    lda stack_value+1
    jmp cpu8088_mem_write_u8
stack_failed:
    rts

cpu8088_pop_u16:
    jsr stack_address
    jsr cpu8088_mem_read_u8
    bcs @pop_failed
    sta stack_value
    jsr stack_next_byte
    jsr cpu8088_mem_read_u8
    bcs @pop_failed
    tax
    lda stack_value
    pha
    clc
    lda cpu8088_state+CPU_SP
    adc #$02
    sta cpu8088_state+CPU_SP
    lda cpu8088_state+CPU_SP+1
    adc #$00
    sta cpu8088_state+CPU_SP+1
    pla
    clc
    rts
@pop_failed:
    rts

stack_address:
    lda cpu8088_state+CPU_SS
    sta cpu8088_segment
    lda cpu8088_state+CPU_SS+1
    sta cpu8088_segment+1
    lda cpu8088_state+CPU_SP
    sta cpu8088_offset
    lda cpu8088_state+CPU_SP+1
    sta cpu8088_offset+1
    jmp cpu8088_segment_offset_physical

stack_next_byte:
    inc cpu8088_offset
    bne :+
    inc cpu8088_offset+1
:
    jmp cpu8088_segment_offset_physical
