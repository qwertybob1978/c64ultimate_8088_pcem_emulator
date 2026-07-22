.setcpu "6502"

.import io_keyboard_push
.import pic_request_irq

.export host_keyboard_poll
.export host_keyboard_translate

GETIN = $FFE4
XT_KEYBOARD_IRQ = $01

.segment "CODE"

; Poll the C64 KERNAL keyboard buffer and inject one XT set-1 make code.
; Carry is set when a key was delivered. Break codes are intentionally omitted
; for the first BIOS/DOS slice; ordinary BIOS key input consumes make codes.
host_keyboard_poll:
    jsr GETIN
    beq @none
    jsr host_keyboard_translate
    bcc @none
    jsr io_keyboard_push
    lda #XT_KEYBOARD_IRQ
    jsr pic_request_irq
    sec
    rts
@none:
    clc
    rts

; Translate common PETSCII/ASCII key values in A to XT keyboard set-1 scan
; codes. Carry clear means the key is not represented yet.
host_keyboard_translate:
    cmp #$0D
    beq @enter
    cmp #$14
    beq @backspace
    cmp #$20
    beq @space
    cmp #$91
    beq @up
    cmp #$11
    beq @down
    cmp #$9D
    beq @left
    cmp #$1D
    beq @right
    cmp #$85
    bcc @not_function
    cmp #$8D
    bcs @not_function
    sec
    sbc #$85
    tax
    lda function_scan_codes,x
    sec
    rts
@not_function:
    cmp #$30
    bcc @punctuation
    cmp #$3A
    bcc @digit
    cmp #$41
    bcc @punctuation
    cmp #$5B
    bcc @letter
    cmp #$C1
    bcc @unsupported
    cmp #$DB
    bcs @unsupported
    and #$1F                    ; PETSCII shifted letter -> 1..26
    ora #$40
@letter:
    sec
    sbc #$41
    tax
    lda letter_scan_codes,x
    sec
    rts
@digit:
    sec
    sbc #$30
    tax
    lda digit_scan_codes,x
    sec
    rts
@punctuation:
    ldx #$00
@punctuation_next:
    cmp punctuation_chars,x
    beq @punctuation_found
    inx
    cpx #punctuation_count
    bne @punctuation_next
@unsupported:
    lda #$00
    clc
    rts
@punctuation_found:
    lda punctuation_scans,x
    sec
    rts
@enter:
    lda #$1C
    sec
    rts
@backspace:
    lda #$0E
    sec
    rts
@space:
    lda #$39
    sec
    rts
@up:
    lda #$48
    sec
    rts
@down:
    lda #$50
    sec
    rts
@left:
    lda #$4B
    sec
    rts
@right:
    lda #$4D
    sec
    rts

.segment "RODATA"
letter_scan_codes:
    .byte $1E,$30,$2E,$20,$12,$21,$22,$23,$17,$24,$25,$26,$32
    .byte $31,$18,$19,$10,$13,$1F,$14,$16,$2F,$11,$2D,$15,$2C
digit_scan_codes:
    .byte $0B,$02,$03,$04,$05,$06,$07,$08,$09,$0A
; C64 GETIN returns F1,F3,F5,F7,F2,F4,F6,F8 in codes 85h..8Ch.
function_scan_codes:
    .byte $3B,$3D,$3F,$41,$3C,$3E,$40,$42
punctuation_chars:
    .byte $2D,$3D,$2C,$2E,$2F,$3B
punctuation_scans:
    .byte $0C,$0D,$33,$34,$35,$27
punctuation_count = *-punctuation_scans
