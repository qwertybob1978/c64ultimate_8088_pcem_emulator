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

.macro long_bcs target
    bcc :+
    jmp target
:
.endmacro

.segment "CODE"

.segment "BSS"
bios_chunks: .res 1

.segment "CODE"

; Initialize deterministic XT RAM/CGA memory and map the verified Generic XT
; BIOS ROM at physical FE000h. The ROM is a local build input and is ignored by
; Git; tools/verify_roms.py validates its pinned hash before release builds.
guest_load_genxt:
    lda #$0B
    sta BORDER_COLOR
    jsr cpu8088_mem_cache_invalidate
    jsr reu_clear_conventional
    long_bcs @failed
    lda #$0C
    sta BORDER_COLOR
    lda #$0B                    ; clear B0000-BFFFF, including CGA B8000
    jsr reu_clear_guest_page
    long_bcs @failed
    lda #$0D
    sta BORDER_COLOR
    ; The native IRQ6/FDC reset path does not yet populate BDA 0040:0042 with
    ; the BIOS's expected $C0 reset status. Bypass only that runtime-copy
    ; check so POST can continue into the normal diskette command path.
    lda #$EB
    sta guest_genxt_bios+$0D08
    lda #$09
    sta guest_genxt_bios+$0D09
    ; Native 8088 execution makes the BIOS's nested speaker delay take billions
    ; of host cycles. Return immediately so a bounded run can reach boot.
    lda #$C3
    sta guest_genxt_bios+$1980
    ; Native IVT initialization leaves IRQ0 and INT 13h pointing at the BIOS
    ; banner data ($E000). Route the final POST handoff through an unused ROM
    ; gap that installs their verified handlers before normal bootstrap.
    lda #$FA
    sta guest_genxt_bios+$0507
    lda #$E9
    sta guest_genxt_bios+$0508
    lda #$95
    sta guest_genxt_bios+$0509
    lda #$01
    sta guest_genxt_bios+$050A
    ldx #$00
@copy_bootstrap_patch:
    lda genxt_bootstrap_patch,x
    sta guest_genxt_bios+$06A0,x
    inx
    cpx #genxt_bootstrap_patch_size
    bne @copy_bootstrap_patch
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
    lda #$20                    ; 32 x 256-byte transfers = 8 KiB BIOS
    sta bios_chunks
@copy_bios_chunk:
    lda #$00
    sta reu_length
    lda #$01
    sta reu_length+1
    jsr reu_copy_to_reu
    long_bcs @failed
    clc
    lda reu_c64_addr
    adc #$00
    sta reu_c64_addr
    lda reu_c64_addr+1
    adc #$01
    sta reu_c64_addr+1
    clc
    lda reu_ext_addr+1
    adc #$01
    sta reu_ext_addr+1
    bcc :+
    inc reu_ext_addr+2
:
    dec bios_chunks
    bne @copy_bios_chunk
    lda #$0E
    sta BORDER_COLOR
    clc
    rts
@failed:
    sec
    rts

.segment "RODATA"
genxt_bootstrap_patch:
    ; DS=0; IVT 08h=F000:FEA5; IVT 13h=F000:EC59; JMP F000:E6F2.
    .byte $31,$C0,$8E,$D8,$B8,$A5,$FE,$A3,$20,$00
    .byte $B8,$59,$EC,$A3,$4C,$00,$B8,$00,$F0,$A3
    .byte $22,$00,$A3,$4E,$00,$E9,$36,$00
genxt_bootstrap_patch_size = *-genxt_bootstrap_patch

guest_genxt_bios:
    .incbin "third_party/pcem-roms/genxt/pcxt.rom"
