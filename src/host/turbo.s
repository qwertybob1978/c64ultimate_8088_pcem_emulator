.setcpu "6502"

.include "host/hardware.inc"

.export turbo_detect
.export turbo_enable_max
.export turbo_restore

.segment "BSS"
turbo_saved_control: .res 1
turbo_available:     .res 1

.segment "CODE"

; Detect the writable Ultimate turbo register without relying on its initial
; value. Returns carry set when present. The original setting is restored.
turbo_detect:
    lda U64_TURBO_CONTROL
    and #$8F
    sta turbo_saved_control

    lda #$80
    sta U64_TURBO_CONTROL
    lda U64_TURBO_CONTROL
    and #$8F
    cmp #$80
    bne @not_available

    lda #$01
    sta turbo_available
    lda turbo_saved_control
    sta U64_TURBO_CONTROL
    sec
    rts

@not_available:
    lda #$00
    sta turbo_available
    lda turbo_saved_control
    sta U64_TURBO_CONTROL
    clc
    rts

; Select the maximum speed index and permit internal-memory execution during
; VIC badlines. Call turbo_restore before returning to another program.
turbo_enable_max:
    lda turbo_available
    bne @enable
    jsr turbo_detect
    bcc @unavailable
@enable:
    lda #U64_TURBO_MAX
    sta U64_TURBO_CONTROL
    sec
    rts
@unavailable:
    clc
    rts

turbo_restore:
    lda turbo_available
    beq @done
    lda turbo_saved_control
    sta U64_TURBO_CONTROL
@done:
    rts

