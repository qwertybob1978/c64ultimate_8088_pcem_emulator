.setcpu "6502"

.include "cpu8088/state.inc"

.export cpu8088_reset
.export cpu8088_state
.export cpu8088_halted
.export cpu8088_last_cycles

.segment "BSS"
cpu8088_state: .res CPU_STATE_SIZE
cpu8088_halted: .res 1
cpu8088_last_cycles: .res 1

.segment "CODE"

; 8088 reset state used by PC/XT hardware: CS:IP = FFFF:0000, FLAGS bit 1 set,
; and general/remaining segment registers cleared. Physical execution begins at
; $FFFF0.
cpu8088_reset:
    lda #$00
    sta cpu8088_halted
    sta cpu8088_last_cycles
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
