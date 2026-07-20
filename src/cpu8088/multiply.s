.setcpu "6502"

.include "cpu8088/state.inc"

.import cpu8088_state

.export cpu8088_mul_u8
.export cpu8088_mul_s8
.export cpu8088_mul_u16
.export cpu8088_mul_s16

.segment "BSS"
mul_multiplier:   .res 2
mul_multiplicand: .res 4
mul_product:      .res 4
mul_count:        .res 1
mul_negative:     .res 1

.segment "CODE"

; AL * A -> AX. Carry is set when AH is not zero.
cpu8088_mul_u8:
    sta mul_multiplier
    lda #$00
    sta mul_multiplier+1
    lda cpu8088_state+CPU_AX
    sta mul_multiplicand
    lda #$00
    sta mul_multiplicand+1
    sta mul_multiplicand+2
    sta mul_multiplicand+3
    lda #$08
    jsr multiply_unsigned
    lda mul_product
    sta cpu8088_state+CPU_AX
    lda mul_product+1
    sta cpu8088_state+CPU_AX+1
    beq @u8_fits
    sec
    rts
@u8_fits:
    clc
    rts

; Signed AL * signed A -> AX. Carry is set unless AH sign-extends AL.
cpu8088_mul_s8:
    sta mul_multiplier
    eor cpu8088_state+CPU_AX
    and #$80
    sta mul_negative
    lda cpu8088_state+CPU_AX
    bpl :+
    eor #$FF
    clc
    adc #$01
    sta cpu8088_state+CPU_AX
:
    lda mul_multiplier
    bpl :+
    eor #$FF
    clc
    adc #$01
    sta mul_multiplier
:
    lda mul_multiplier
    jsr cpu8088_mul_u8
    lda mul_negative
    beq @signed8_test
    sec
    lda #$00
    sbc cpu8088_state+CPU_AX
    sta cpu8088_state+CPU_AX
    lda #$00
    sbc cpu8088_state+CPU_AX+1
    sta cpu8088_state+CPU_AX+1
@signed8_test:
    lda cpu8088_state+CPU_AX
    bmi :+
    lda cpu8088_state+CPU_AX+1
    beq @signed8_fits
    sec
    rts
@signed8_fits:
    clc
    rts
:
    lda cpu8088_state+CPU_AX+1
    cmp #$FF
    beq @signed8_fits
    sec
    rts

; AX * X:A -> DX:AX. Carry is set when DX is not zero.
cpu8088_mul_u16:
    sta mul_multiplier
    stx mul_multiplier+1
    lda cpu8088_state+CPU_AX
    sta mul_multiplicand
    lda cpu8088_state+CPU_AX+1
    sta mul_multiplicand+1
    lda #$00
    sta mul_multiplicand+2
    sta mul_multiplicand+3
    lda #$10
    jsr multiply_unsigned
    jsr store_product32
    lda cpu8088_state+CPU_DX
    ora cpu8088_state+CPU_DX+1
    beq @u16_fits
    sec
    rts
@u16_fits:
    clc
    rts

; Signed AX * signed X:A -> DX:AX. Carry is set unless DX sign-extends AX.
cpu8088_mul_s16:
    sta mul_multiplier
    stx mul_multiplier+1
    txa
    eor cpu8088_state+CPU_AX+1
    and #$80
    sta mul_negative
    lda cpu8088_state+CPU_AX+1
    bpl :+
    sec
    lda #$00
    sbc cpu8088_state+CPU_AX
    sta cpu8088_state+CPU_AX
    lda #$00
    sbc cpu8088_state+CPU_AX+1
    sta cpu8088_state+CPU_AX+1
:
    lda mul_multiplier+1
    bpl :+
    sec
    lda #$00
    sbc mul_multiplier
    sta mul_multiplier
    lda #$00
    sbc mul_multiplier+1
    sta mul_multiplier+1
:
    lda mul_multiplier
    ldx mul_multiplier+1
    jsr cpu8088_mul_u16
    lda mul_negative
    beq @signed16_test
    sec
    lda #$00
    sbc cpu8088_state+CPU_AX
    sta cpu8088_state+CPU_AX
    lda #$00
    sbc cpu8088_state+CPU_AX+1
    sta cpu8088_state+CPU_AX+1
    lda #$00
    sbc cpu8088_state+CPU_DX
    sta cpu8088_state+CPU_DX
    lda #$00
    sbc cpu8088_state+CPU_DX+1
    sta cpu8088_state+CPU_DX+1
@signed16_test:
    lda cpu8088_state+CPU_AX+1
    bmi :+
    lda cpu8088_state+CPU_DX
    ora cpu8088_state+CPU_DX+1
    beq @signed16_fits
    sec
    rts
:
    lda cpu8088_state+CPU_DX
    cmp #$FF
    bne @signed16_overflow
    lda cpu8088_state+CPU_DX+1
    cmp #$FF
    beq @signed16_fits
@signed16_overflow:
    sec
    rts
@signed16_fits:
    clc
    rts

; A is the bit count. The caller initializes multiplier and multiplicand.
multiply_unsigned:
    sta mul_count
    lda #$00
    sta mul_product
    sta mul_product+1
    sta mul_product+2
    sta mul_product+3
@loop:
    lsr mul_multiplier+1
    ror mul_multiplier
    bcc @shift
    clc
    lda mul_product
    adc mul_multiplicand
    sta mul_product
    lda mul_product+1
    adc mul_multiplicand+1
    sta mul_product+1
    lda mul_product+2
    adc mul_multiplicand+2
    sta mul_product+2
    lda mul_product+3
    adc mul_multiplicand+3
    sta mul_product+3
@shift:
    asl mul_multiplicand
    rol mul_multiplicand+1
    rol mul_multiplicand+2
    rol mul_multiplicand+3
    dec mul_count
    bne @loop
    rts

store_product32:
    lda mul_product
    sta cpu8088_state+CPU_AX
    lda mul_product+1
    sta cpu8088_state+CPU_AX+1
    lda mul_product+2
    sta cpu8088_state+CPU_DX
    lda mul_product+3
    sta cpu8088_state+CPU_DX+1
    rts
