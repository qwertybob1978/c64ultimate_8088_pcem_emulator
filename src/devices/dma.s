.setcpu "6502"

.import reu_copy_from_reu
.import reu_copy_to_reu
.import cpu8088_mem_cache_invalidate
.import cpu8088_mem_cache_flush
.import cpu8088_fetch_cache_invalidate
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.export dma_reset
.export dma_read_u8
.export dma_write_u8
.export dma_channel2_read_from_reu

.segment "BSS"
dma_channel2_addr:      .res 2
dma_channel2_count:     .res 2
dma_channel2_page:      .res 1
dma_channel2_mode:      .res 1
dma_channel2_masked:    .res 1
dma_flipflop:           .res 1
dma_buffer:             .res 256
dma_source_addr:        .res 3
dma_guest_addr:         .res 3

.segment "CODE"

dma_reset:
    lda #$00
    sta dma_channel2_addr
    sta dma_channel2_addr+1
    sta dma_channel2_count
    sta dma_channel2_count+1
    sta dma_channel2_page
    sta dma_channel2_mode
    sta dma_flipflop
    lda #$01
    sta dma_channel2_masked
    rts

dma_read_u8:
    cpx #$04
    beq @read_addr
    cpx #$05
    beq @read_count
    lda #$00
    rts
@read_addr:
    lda dma_flipflop
    beq @read_addr_low
    lda #$00
    sta dma_flipflop
    lda dma_channel2_addr+1
    rts
@read_addr_low:
    lda #$01
    sta dma_flipflop
    lda dma_channel2_addr
    rts
@read_count:
    lda dma_flipflop
    beq @read_count_low
    lda #$00
    sta dma_flipflop
    lda dma_channel2_count+1
    rts
@read_count_low:
    lda #$01
    sta dma_flipflop
    lda dma_channel2_count
    rts

dma_write_u8:
    cpx #$04
    beq @write_addr
    cpx #$05
    beq @write_count
    cpx #$08
    beq @ignore
    cpx #$0A
    beq @write_mask
    cpx #$0B
    beq @write_mode
    cpx #$0C
    beq @clear_flipflop
    cpx #$0D
    beq @master_clear
    cpx #$81
    beq @write_page
@ignore:
    rts
@write_addr:
    ldy dma_flipflop
    bne @write_addr_high
    sta dma_channel2_addr
    iny
    sty dma_flipflop
    rts
@write_addr_high:
    sta dma_channel2_addr+1
    lda #$00
    sta dma_flipflop
    rts
@write_count:
    ldy dma_flipflop
    bne @write_count_high
    sta dma_channel2_count
    iny
    sty dma_flipflop
    rts
@write_count_high:
    sta dma_channel2_count+1
    lda #$00
    sta dma_flipflop
    rts
@write_mask:
    pha
    and #$03
    cmp #$02
    beq :+
    pla
    rts
:
    pla
    and #$04
    beq :+
    lda #$01
    sta dma_channel2_masked
    rts
:
    lda #$00
    sta dma_channel2_masked
    rts
@write_mode:
    pha
    and #$03
    cmp #$02
    bne @write_mode_done
    pla
    sta dma_channel2_mode
    rts
@write_mode_done:
    pla
    rts
@clear_flipflop:
    lda #$00
    sta dma_flipflop
    rts
@master_clear:
    jmp dma_reset
@write_page:
    sta dma_channel2_page
    rts

; Source REU address is supplied in reu_ext_addr. Copy one 512-byte sector into
; the current channel-2 guest physical address and advance the DMA registers.
dma_channel2_read_from_reu:
    lda dma_channel2_masked
    beq :+
    jmp @failed
:
    lda dma_channel2_count+1
    cmp #$01
    bcs :+
    jmp @failed
:
    bne @count_ok
    lda dma_channel2_count
    cmp #$FF
    bcs :+
    jmp @failed
:
@count_ok:
    ; Preserve the FDC source pointer because cache flush reuses REU address
    ; registers. Then flush dirty guest RAM before direct DMA bypasses cache.
    lda reu_ext_addr
    sta dma_source_addr
    lda reu_ext_addr+1
    sta dma_source_addr+1
    lda reu_ext_addr+2
    sta dma_source_addr+2
    jsr cpu8088_mem_cache_flush
    bcc :+
    jmp @failed
:
    lda dma_channel2_addr
    sta dma_guest_addr
    lda dma_channel2_addr+1
    sta dma_guest_addr+1
    lda dma_channel2_page
    and #$0F
    sta dma_guest_addr+2

    lda #<dma_buffer
    sta reu_c64_addr
    lda #>dma_buffer
    sta reu_c64_addr+1
    lda #$00
    sta reu_length
    lda #$01
    sta reu_length+1

    lda dma_source_addr
    sta reu_ext_addr
    lda dma_source_addr+1
    sta reu_ext_addr+1
    lda dma_source_addr+2
    sta reu_ext_addr+2
    jsr reu_copy_from_reu
    bcs @failed

    lda dma_guest_addr
    sta reu_ext_addr
    lda dma_guest_addr+1
    sta reu_ext_addr+1
    lda dma_guest_addr+2
    sta reu_ext_addr+2
    jsr reu_copy_to_reu
    bcs @failed

    inc dma_source_addr+1
    bne :+
    inc dma_source_addr+2
:
    inc dma_guest_addr+1
    bne :+
    inc dma_guest_addr+2
:

    lda dma_source_addr
    sta reu_ext_addr
    lda dma_source_addr+1
    sta reu_ext_addr+1
    lda dma_source_addr+2
    sta reu_ext_addr+2
    jsr reu_copy_from_reu
    bcs @failed

    lda dma_guest_addr
    sta reu_ext_addr
    lda dma_guest_addr+1
    sta reu_ext_addr+1
    lda dma_guest_addr+2
    sta reu_ext_addr+2
    jsr reu_copy_to_reu
    bcs @failed

    clc
    lda dma_channel2_addr
    adc #$00
    sta dma_channel2_addr
    lda dma_channel2_addr+1
    adc #$02
    sta dma_channel2_addr+1

    sec
    lda dma_channel2_count
    sbc #$00
    sta dma_channel2_count
    lda dma_channel2_count+1
    sbc #$02
    sta dma_channel2_count+1

    jsr cpu8088_mem_cache_invalidate
    jsr cpu8088_fetch_cache_invalidate
    clc
    rts
@failed:
    sec
    rts
