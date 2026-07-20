.setcpu "6502"

.include "cpu8088/state.inc"

.import cpu8088_state
.import cpu8088_fetch_u8
.import cpu8088_segment_offset_physical
.importzp cpu8088_segment
.importzp cpu8088_offset

.export cpu8088_decode_ea
.export cpu8088_ea_next_byte
.export cpu8088_ea_recompute
.export cpu8088_ea_rm_index

.segment "ZEROPAGE"
cpu8088_ea_offset:  .res 2
cpu8088_ea_segment: .res 2

EA_MEMORY = $00
EA_REGISTER = $01
EA_ERROR = $FE

.segment "BSS"
ea_modrm:          .res 1
ea_mod:            .res 1
cpu8088_ea_rm_index: .res 1
ea_segment_offset: .res 1
ea_displacement:   .res 1

.segment "CODE"

; Decode the r/m half of a ModR/M byte in A. Returns EA_REGISTER for mod=3.
; Otherwise computes the default-segment physical address and returns
; EA_MEMORY. Displacements are consumed from CS:IP through the fetch cache.
cpu8088_decode_ea:
    sta ea_modrm
    and #$07
    sta cpu8088_ea_rm_index
    lda ea_modrm
    and #$C0
    sta ea_mod
    cmp #$C0
    bne @memory
    lda #EA_REGISTER
    rts

@memory:
    lda #CPU_DS
    sta ea_segment_offset
    lda #$00
    sta cpu8088_ea_offset
    sta cpu8088_ea_offset+1

    lda cpu8088_ea_rm_index
    cmp #$00
    beq @bx_si
    cmp #$01
    beq @bx_di
    cmp #$02
    beq @bp_si
    cmp #$03
    beq @bp_di
    cmp #$04
    beq @si
    cmp #$05
    beq @di
    cmp #$06
    beq @bp_or_direct
    ldx #CPU_BX
    jsr @add_register
    jmp @displacement
@bx_si:
    ldx #CPU_BX
    jsr @add_register
@si:
    ldx #CPU_SI
    jsr @add_register
    jmp @displacement
@bx_di:
    ldx #CPU_BX
    jsr @add_register
@di:
    ldx #CPU_DI
    jsr @add_register
    jmp @displacement
@bp_si:
    ldx #CPU_BP
    jsr @add_register
    ldx #CPU_SI
    jsr @add_register
    lda #CPU_SS
    sta ea_segment_offset
    jmp @displacement
@bp_di:
    ldx #CPU_BP
    jsr @add_register
    ldx #CPU_DI
    jsr @add_register
    lda #CPU_SS
    sta ea_segment_offset
    jmp @displacement
@bp_or_direct:
    lda ea_mod
    bne @bp
    jsr cpu8088_fetch_u8
    bcs @error
    sta cpu8088_ea_offset
    jsr cpu8088_fetch_u8
    bcs @error
    sta cpu8088_ea_offset+1
    jmp @finish
@bp:
    ldx #CPU_BP
    jsr @add_register
    lda #CPU_SS
    sta ea_segment_offset

@displacement:
    lda ea_mod
    beq @finish
    cmp #$40
    beq @disp8
    jsr cpu8088_fetch_u8
    bcs @error
    sta ea_displacement
    jsr cpu8088_fetch_u8
    bcs @error
    clc
    adc cpu8088_ea_offset+1
    sta cpu8088_ea_offset+1
    lda ea_displacement
    clc
    adc cpu8088_ea_offset
    sta cpu8088_ea_offset
    bcc @finish
    inc cpu8088_ea_offset+1
    jmp @finish
@disp8:
    jsr cpu8088_fetch_u8
    bcs @error
    sta ea_displacement
    clc
    adc cpu8088_ea_offset
    sta cpu8088_ea_offset
    lda ea_displacement
    bpl @disp8_positive
    lda #$FF
    bne @disp8_high
@disp8_positive:
    lda #$00
@disp8_high:
    adc cpu8088_ea_offset+1
    sta cpu8088_ea_offset+1

@finish:
    ldx ea_segment_offset
    lda cpu8088_state,x
    sta cpu8088_ea_segment
    sta cpu8088_segment
    lda cpu8088_state+1,x
    sta cpu8088_ea_segment+1
    sta cpu8088_segment+1
    lda cpu8088_ea_offset
    sta cpu8088_offset
    lda cpu8088_ea_offset+1
    sta cpu8088_offset+1
    jsr cpu8088_segment_offset_physical
    lda #EA_MEMORY
    rts
@error:
    lda #EA_ERROR
    rts

@add_register:
    clc
    lda cpu8088_ea_offset
    adc cpu8088_state,x
    sta cpu8088_ea_offset
    lda cpu8088_ea_offset+1
    adc cpu8088_state+1,x
    sta cpu8088_ea_offset+1
    rts

cpu8088_ea_next_byte:
    inc cpu8088_ea_offset
    bne :+
    inc cpu8088_ea_offset+1
:
cpu8088_ea_recompute:
    lda cpu8088_ea_segment
    sta cpu8088_segment
    lda cpu8088_ea_segment+1
    sta cpu8088_segment+1
    lda cpu8088_ea_offset
    sta cpu8088_offset
    lda cpu8088_ea_offset+1
    sta cpu8088_offset+1
    jmp cpu8088_segment_offset_physical
