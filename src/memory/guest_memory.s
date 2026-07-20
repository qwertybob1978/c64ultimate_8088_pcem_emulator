.setcpu "6502"

.importzp cpu8088_phys_addr
.import reu_copy_from_reu
.import reu_copy_to_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length
.import cpu8088_fetch_cache_write_u8

.export cpu8088_mem_read_u8
.export cpu8088_mem_write_u8
.export cpu8088_mem_cache_invalidate
.export cpu8088_mem_cache_flush
.export cpu8088_mem_cache_misses

.segment "BSS"
guest_data_page:          .res 256
guest_data_byte:          .res 1
guest_page_tag_mid:       .res 1
guest_page_tag_high:      .res 1
guest_page_valid:         .res 1
guest_page_dirty:         .res 1
cpu8088_mem_cache_misses: .res 2

.segment "CODE"

cpu8088_mem_cache_invalidate:
    lda #$00
    sta guest_page_valid
    sta guest_page_dirty
    rts

; Read one byte through a 256-byte page cache. BIOS POST repeatedly scans and
; compares adjacent RAM bytes, so replacing each byte DMA with one page DMA is
; the largest safe early optimization. Dirty pages are written back on a miss
; or explicit flush; direct REU clients must flush first.
cpu8088_mem_read_u8:
    lda guest_page_valid
    beq @refill
    lda cpu8088_phys_addr+1
    cmp guest_page_tag_mid
    bne @refill
    lda cpu8088_phys_addr+2
    cmp guest_page_tag_high
    beq @read_cached

@refill:
    jsr guest_refill_page
    bcs @failed

@read_cached:
    ldy cpu8088_phys_addr
    lda guest_data_page,y
    clc
@failed:
    rts

; Allocate writes in the same cache. This makes the BIOS RAM test one page
; refill plus one page write-back instead of hundreds of one-byte transfers.
cpu8088_mem_write_u8:
    sta guest_data_byte
    lda guest_page_valid
    beq @refill
    lda cpu8088_phys_addr+1
    cmp guest_page_tag_mid
    bne @refill
    lda cpu8088_phys_addr+2
    cmp guest_page_tag_high
    beq @write_cached
@refill:
    jsr guest_refill_page
    bcs @write_failed
@write_cached:
    ldy cpu8088_phys_addr
    lda guest_data_byte
    sta guest_data_page,y
    jsr cpu8088_fetch_cache_write_u8
    lda #$01
    sta guest_page_dirty
    clc
@write_failed:
    rts

; Write the current dirty page to its aligned REU address. Carry is clear when
; no write is needed or after a successful transfer.
cpu8088_mem_cache_flush:
    lda guest_page_valid
    beq @nothing
    lda guest_page_dirty
    beq @nothing
    lda #<guest_data_page
    sta reu_c64_addr
    lda #>guest_data_page
    sta reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    lda guest_page_tag_mid
    sta reu_ext_addr+1
    lda guest_page_tag_high
    sta reu_ext_addr+2
    lda #$00
    sta reu_length
    lda #$01
    sta reu_length+1
    jsr reu_copy_to_reu
    bcs @flush_failed
    lda #$00
    sta guest_page_dirty
@nothing:
    clc
@flush_failed:
    rts

guest_refill_page:
    jsr cpu8088_mem_cache_flush
    bcs @refill_failed
    lda #<guest_data_page
    sta reu_c64_addr
    lda #>guest_data_page
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
    bcs @refill_failed
    lda cpu8088_phys_addr+1
    sta guest_page_tag_mid
    lda cpu8088_phys_addr+2
    sta guest_page_tag_high
    lda #$01
    sta guest_page_valid
    lda #$00
    sta guest_page_dirty
    inc cpu8088_mem_cache_misses
    bne @refill_done
    inc cpu8088_mem_cache_misses+1
@refill_done:
    clc
@refill_failed:
    rts
