.setcpu "6502"

.include "cpu8088/state.inc"

.import cpu8088_state

.export cpu8088_div_u8
.export cpu8088_div_s8
.export cpu8088_div_u16
.export cpu8088_div_s16

.segment "BSS"
divisor:          .res 2
quotient:         .res 2
remainder:        .res 2
divide_count:     .res 1
dividend_negative:.res 1
quotient_negative:.res 1
saved_dividend:   .res 4

.segment "CODE"

; AX / A -> AL quotient, AH remainder. Carry means zero divisor or overflow.
cpu8088_div_u8:
    sta divisor
    beq @error
    lda cpu8088_state+CPU_AX+1
    cmp divisor
    bcs @error                  ; quotient cannot fit in AL
    sta remainder
    lda cpu8088_state+CPU_AX
    sta quotient
    lda #$08
    sta divide_count
@loop:
    asl quotient
    rol remainder
    bcs @subtract
    lda remainder
    cmp divisor
    bcc :+
@subtract:
    sbc divisor
    sta remainder
    inc quotient
:
    dec divide_count
    bne @loop
    lda quotient
    sta cpu8088_state+CPU_AX
    lda remainder
    sta cpu8088_state+CPU_AX+1
    clc
    rts
@error:
    jmp divide_error

; DX:AX / X:A -> AX quotient, DX remainder.
cpu8088_div_u16:
    sta divisor
    stx divisor+1
    ora divisor+1
    bne :+
    jmp @error
:
    lda cpu8088_state+CPU_DX+1
    cmp divisor+1
    bcc @fits
    beq :+
    jmp @error
:
    lda cpu8088_state+CPU_DX
    cmp divisor
    bcc @fits
    jmp @error
@fits:
    lda cpu8088_state+CPU_AX
    sta quotient
    lda cpu8088_state+CPU_AX+1
    sta quotient+1
    lda cpu8088_state+CPU_DX
    sta remainder
    lda cpu8088_state+CPU_DX+1
    sta remainder+1
    lda #$10
    sta divide_count
@loop:
    asl quotient
    rol quotient+1
    rol remainder
    rol remainder+1
    bcs @subtract
    lda remainder+1
    cmp divisor+1
    bcc @next
    bne @subtract
    lda remainder
    cmp divisor
    bcc @next
@subtract:
    sec
    lda remainder
    sbc divisor
    sta remainder
    lda remainder+1
    sbc divisor+1
    sta remainder+1
    inc quotient
@next:
    dec divide_count
    bne @loop
    lda quotient
    sta cpu8088_state+CPU_AX
    lda quotient+1
    sta cpu8088_state+CPU_AX+1
    lda remainder
    sta cpu8088_state+CPU_DX
    lda remainder+1
    sta cpu8088_state+CPU_DX+1
    clc
    rts
@error:
    jmp divide_error

; Signed AX / signed A -> signed AL quotient, signed AH remainder.
cpu8088_div_s8:
    sta divisor
    jsr save_ax_dx
    lda cpu8088_state+CPU_AX+1
    and #$80
    sta dividend_negative
    lda divisor
    eor cpu8088_state+CPU_AX+1
    and #$80
    sta quotient_negative
    lda dividend_negative
    beq :+
    jsr negate_ax
:
    lda divisor
    bpl :+
    eor #$FF
    clc
    adc #$01
    sta divisor
:
    lda divisor
    jsr cpu8088_div_u8
    bcs signed8_restore_error
    lda cpu8088_state+CPU_AX
    ldx quotient_negative
    beq @positive_limit
    cmp #$81
    bcs signed8_restore_error
    jsr negate_al
    jmp @remainder
@positive_limit:
    cmp #$80
    bcs signed8_restore_error
@remainder:
    lda dividend_negative
    beq signed_divide_ok
    jsr negate_ah
signed_divide_ok:
    clc
    rts
signed8_restore_error:
    jmp restore_divide_error

; Signed DX:AX / signed X:A -> signed AX quotient, signed DX remainder.
cpu8088_div_s16:
    sta divisor
    stx divisor+1
    jsr save_ax_dx
    lda cpu8088_state+CPU_DX+1
    and #$80
    sta dividend_negative
    lda divisor+1
    eor cpu8088_state+CPU_DX+1
    and #$80
    sta quotient_negative
    lda dividend_negative
    beq :+
    jsr negate_dx_ax
:
    lda divisor+1
    bpl :+
    jsr negate_divisor
:
    lda divisor
    ldx divisor+1
    jsr cpu8088_div_u16
    bcs restore_divide_error
    lda cpu8088_state+CPU_AX+1
    ldx quotient_negative
    beq @positive_limit
    cmp #$80
    bcc @apply_quotient_sign
    bne restore_divide_error
    lda cpu8088_state+CPU_AX
    bne restore_divide_error
@apply_quotient_sign:
    jsr negate_ax
    jmp @word_remainder
@positive_limit:
    lda cpu8088_state+CPU_AX+1
    bmi restore_divide_error
@word_remainder:
    lda dividend_negative
    beq signed_divide_ok
    jsr negate_dx
    clc
    rts

save_ax_dx:
    lda cpu8088_state+CPU_AX
    sta saved_dividend
    lda cpu8088_state+CPU_AX+1
    sta saved_dividend+1
    lda cpu8088_state+CPU_DX
    sta saved_dividend+2
    lda cpu8088_state+CPU_DX+1
    sta saved_dividend+3
    rts

restore_divide_error:
    lda saved_dividend
    sta cpu8088_state+CPU_AX
    lda saved_dividend+1
    sta cpu8088_state+CPU_AX+1
    lda saved_dividend+2
    sta cpu8088_state+CPU_DX
    lda saved_dividend+3
    sta cpu8088_state+CPU_DX+1
divide_error:
    sec
    rts

negate_al:
    lda cpu8088_state+CPU_AX
    eor #$FF
    clc
    adc #$01
    sta cpu8088_state+CPU_AX
    rts

negate_ah:
    lda cpu8088_state+CPU_AX+1
    eor #$FF
    clc
    adc #$01
    sta cpu8088_state+CPU_AX+1
    rts

negate_ax:
    sec
    lda #$00
    sbc cpu8088_state+CPU_AX
    sta cpu8088_state+CPU_AX
    lda #$00
    sbc cpu8088_state+CPU_AX+1
    sta cpu8088_state+CPU_AX+1
    rts

negate_dx:
    sec
    lda #$00
    sbc cpu8088_state+CPU_DX
    sta cpu8088_state+CPU_DX
    lda #$00
    sbc cpu8088_state+CPU_DX+1
    sta cpu8088_state+CPU_DX+1
    rts

negate_dx_ax:
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
    rts

negate_divisor:
    sec
    lda #$00
    sbc divisor
    sta divisor
    lda #$00
    sbc divisor+1
    sta divisor+1
    rts
