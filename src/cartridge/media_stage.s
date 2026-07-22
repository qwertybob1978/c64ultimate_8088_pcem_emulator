.setcpu "6502"

.import reu_copy_to_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.export cartridge_stage_media

MAGIC_DESK_BANK = $DE00
CARTRIDGE_WINDOW = $8000
MEDIA_DESCRIPTOR = $81F0
MEDIA_SIGNATURE = $4D

.segment "BSS"
media_bank:      .res 1
media_remaining: .res 3

.segment "CODE"

; Stage the optional boot disk from cartridge banks into REU, then disable the
; cartridge window so the rest of the payload runs against normal C64 memory.
; Carry set reports an REU transfer failure.
cartridge_stage_media:
    lda MEDIA_DESCRIPTOR
    cmp #MEDIA_SIGNATURE
    beq :+
    jmp @disable_only
:
    lda MEDIA_DESCRIPTOR+1
    bne :+
    jmp @disable_only
:
    lda MEDIA_DESCRIPTOR+2
    sta media_bank
    lda MEDIA_DESCRIPTOR+3
    sta media_remaining
    lda MEDIA_DESCRIPTOR+4
    sta media_remaining+1
    lda MEDIA_DESCRIPTOR+5
    sta media_remaining+2
    lda MEDIA_DESCRIPTOR+6
    sta reu_ext_addr
    lda MEDIA_DESCRIPTOR+7
    sta reu_ext_addr+1
    lda MEDIA_DESCRIPTOR+8
    sta reu_ext_addr+2
@copy_next_bank:
    lda media_remaining
    ora media_remaining+1
    ora media_remaining+2
    beq @disable_only
    lda media_bank
    sta MAGIC_DESK_BANK
    lda #<CARTRIDGE_WINDOW
    sta reu_c64_addr
    lda #>CARTRIDGE_WINDOW
    sta reu_c64_addr+1
    lda media_remaining+2
    bne @full_chunk
    lda media_remaining+1
    cmp #$20
    bcc @partial_chunk
    bne @full_chunk
    lda media_remaining
    beq @full_chunk
@partial_chunk:
    lda media_remaining
    sta reu_length
    lda media_remaining+1
    sta reu_length+1
    jmp @have_length
@full_chunk:
    lda #$00
    sta reu_length
    lda #$20
    sta reu_length+1
@have_length:
    jsr reu_copy_to_reu
    bcs @failed
    clc
    lda reu_ext_addr
    adc reu_length
    sta reu_ext_addr
    lda reu_ext_addr+1
    adc reu_length+1
    sta reu_ext_addr+1
    lda reu_ext_addr+2
    adc #$00
    sta reu_ext_addr+2
    sec
    lda media_remaining
    sbc reu_length
    sta media_remaining
    lda media_remaining+1
    sbc reu_length+1
    sta media_remaining+1
    lda media_remaining+2
    sbc #$00
    sta media_remaining+2
    inc media_bank
    jmp @copy_next_bank
@disable_only:
    lda #$80
    sta MAGIC_DESK_BANK
    clc
    rts
@failed:
    lda #$80
    sta MAGIC_DESK_BANK
    sec
    rts
