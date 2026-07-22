.setcpu "6502"

.import reu_clear_conventional
.import reu_clear_guest_page
.import reu_copy_to_reu
.importzp reu_c64_addr
.importzp reu_ext_addr
.importzp reu_length
.import cpu8088_mem_cache_invalidate

BORDER_COLOR = $D020

.export guest_load_genxt

.segment "CODE"

; Initialize deterministic XT RAM/CGA memory and map the verified Generic XT
; BIOS ROM at physical FE000h. The ROM is a local build input and is ignored by
; Git; tools/verify_roms.py validates its pinned hash before release builds.
guest_load_genxt:
    lda #$0B
    sta BORDER_COLOR
    jsr cpu8088_mem_cache_invalidate
    jsr reu_clear_conventional
    bcs @failed
    lda #$0C
    sta BORDER_COLOR
    lda #$0B                    ; clear B0000-BFFFF, including CGA B8000
    jsr reu_clear_guest_page
    bcs @failed
    lda #$0D
    sta BORDER_COLOR
    lda #<guest_genxt_bios
    sta reu_c64_addr
    lda #>guest_genxt_bios
    sta reu_c64_addr+1
    lda #$00
    sta reu_ext_addr
    lda #$E0
    sta reu_ext_addr+1
    lda #$0F
    sta reu_ext_addr+2
    lda #$00
    sta reu_length
    lda #$20
    sta reu_length+1
    jsr reu_copy_to_reu
    bcs @failed
    lda #$0E
    sta BORDER_COLOR
@failed:
    rts

.segment "RODATA"
guest_genxt_bios:
    .incbin "third_party/pcem-roms/genxt/pcxt.rom"
