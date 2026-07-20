.setcpu "6502"

.import cpu8088_cs_ip_physical
.import cpu8088_state
.importzp cpu8088_phys_addr
.import reu_copy_from_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length

.include "cpu8088/state.inc"

.export cpu8088_fetch_u8
.export cpu8088_fetch_cache_invalidate
.export cpu8088_fetch_cache_misses

.segment "BSS"
fetch_page:                 .res 256
fetch_page_tag_mid:         .res 1
fetch_page_tag_high:        .res 1
fetch_page_valid:           .res 1
cpu8088_fetch_cache_misses: .res 2

.segment "CODE"

cpu8088_fetch_cache_invalidate:
    lda #$00
    sta fetch_page_valid
    rts

; Fetch one byte through a single 256-byte instruction page held in C64 RAM.
; A cache miss performs one 256-byte REU DMA rather than 256 single-byte DMAs.
; Returns A=byte and carry clear, or carry set if the DMA request was rejected.
cpu8088_fetch_u8:
    jsr cpu8088_cs_ip_physical
    lda fetch_page_valid
    beq @refill
    lda cpu8088_phys_addr+1
    cmp fetch_page_tag_mid
    bne @refill
    lda cpu8088_phys_addr+2
    cmp fetch_page_tag_high
    beq @read_cached

@refill:
    lda #<fetch_page
    sta reu_c64_addr
    lda #>fetch_page
    sta reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    lda cpu8088_phys_addr+1
    sta reu_ext_addr+1
    lda cpu8088_phys_addr+2
    sta reu_ext_addr+2
    lda #$00
    sta reu_length
    lda #$01
    sta reu_length+1
    jsr reu_copy_from_reu
    bcs @failed

    lda cpu8088_phys_addr+1
    sta fetch_page_tag_mid
    lda cpu8088_phys_addr+2
    sta fetch_page_tag_high
    lda #$01
    sta fetch_page_valid
    inc cpu8088_fetch_cache_misses
    bne @read_cached
    inc cpu8088_fetch_cache_misses+1

@read_cached:
    ldy cpu8088_phys_addr
    lda fetch_page,y
    pha
    inc cpu8088_state+CPU_IP
    bne @return_byte
    inc cpu8088_state+CPU_IP+1
@return_byte:
    pla
    clc
@failed:
    rts

