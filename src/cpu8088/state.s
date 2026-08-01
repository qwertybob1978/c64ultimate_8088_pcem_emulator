.setcpu "6502"

.include "cpu8088/state.inc"

.export cpu8088_reset
.export cpu8088_state
.export cpu8088_halted
.export cpu8088_last_cycles
.export cpu8088_segment_override
.export cpu8088_repeat_prefix

.import cpu8088_irq_pending
.import cpu8088_irq_vector
.import cpu8088_nmi_pending
.import cpu8088_interrupt_shadow
.import interrupt_vector
.import cpu8088_interrupt_stage
.import cpu8088_stack_stage
.import interrupt_last_iret_ip
.import interrupt_last_iret_cs
.import interrupt_last_iret_stage
.import interrupt_frame_ip
.import interrupt_frame_cs
.import interrupt_frame_mismatch

.segment "BSS"
cpu8088_state: .res CPU_STATE_SIZE
cpu8088_halted: .res 1
cpu8088_last_cycles: .res 1
cpu8088_segment_override: .res 1
cpu8088_repeat_prefix: .res 1

.segment "CODE"

; 8088 reset state used by PC/XT hardware: CS:IP = FFFF:0000, FLAGS bit 1 set,
; and general/remaining segment registers cleared. Physical execution begins at
; $FFFF0.
cpu8088_reset:
    lda #$00
    sta cpu8088_halted
    sta cpu8088_last_cycles
    sta cpu8088_irq_pending
    sta cpu8088_irq_vector
    sta cpu8088_nmi_pending
    sta cpu8088_interrupt_shadow
    sta interrupt_vector
    sta cpu8088_interrupt_stage
    sta cpu8088_stack_stage
    sta interrupt_last_iret_ip
    sta interrupt_last_iret_ip+1
    sta interrupt_last_iret_cs
    sta interrupt_last_iret_cs+1
    sta interrupt_last_iret_stage
    sta interrupt_frame_ip
    sta interrupt_frame_ip+1
    sta interrupt_frame_cs
    sta interrupt_frame_cs+1
    sta interrupt_frame_mismatch
    ldx #CPU_STATE_SIZE-1
@clear:
    sta cpu8088_state,x
    dex
    bpl @clear

    lda #$FF
    sta cpu8088_state+CPU_CS
    sta cpu8088_state+CPU_CS+1
    lda #<X86_FLAG_RESERVED
    sta cpu8088_state+CPU_FLAGS
    lda #>X86_FLAG_RESERVED
    sta cpu8088_state+CPU_FLAGS+1
    rts
