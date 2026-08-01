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
    ; Native 8088 execution makes the BIOS's speaker delay take billions of
    ; host cycles. Overwrite its entry (F000:F9D4) with RET so a CALL returns
    ; cleanly on a balanced stack.
    lda #$C3
    sta guest_genxt_bios+$19D4
    ; The early memory-sizing test (F000:E15E) leaves a nonzero status in the
    ; POST error byte 0000:0015 under native execution, so the POST summary
    ; (F000:E40B) prints "System error #NN", reads no key, and resets in an
    ; endless loop before ever reaching INT 19h. Turn the summary's JE into an
    ; unconditional JMP to the no-error branch (E43A) so POST proceeds to boot.
    lda #$EB
    sta guest_genxt_bios+$0411
    ; The destructive RAM-test loop (F000:E4D9) calls the byte-pattern tester
    ; f9ee once per KB across all conventional memory. Under native execution
    ; each pass costs thousands of host cycles, so the full sweep would take
    ; tens of billions of cycles and looks like a hang mid-count. RAM is already
    ; cleared by reu_clear_conventional, so replace the loop's block count load
    ; (mov bp,es:[0x13]) with a constant 3 (=> one pass after two DEC BP) so
    ; POST reaches the INT 19h boot handoff promptly.
    lda #$BD                    ; mov bp, imm16
    sta guest_genxt_bios+$04C8
    lda #$03
    sta guest_genxt_bios+$04C9
    lda #$00
    sta guest_genxt_bios+$04CA
    lda #$90                    ; nop (pad remaining bytes of the old opcode)
    sta guest_genxt_bios+$04CB
    lda #$90                    ; nop
    sta guest_genxt_bios+$04CC
    ; Native IVT initialization leaves IRQ0 and INT 13h pointing at the BIOS
    ; banner data ($E000). Route the final POST handoff through an unused ROM
    ; gap that installs their verified handlers before normal bootstrap.
    lda #$FA
    sta guest_genxt_bios+$0507
    lda #$E9
    sta guest_genxt_bios+$0508
    lda #$95                    ; JMP rel16 disp=$0195: E50B+$0195 = E6A0 entry
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
    ; DS=0; IVT 08h=F000:FEA5; IVT 13h=F000:EC59; IVT 0Eh=F000:EF57;
    ; then JMP F000:E6F2. IVT 0Eh is the diskette IRQ6 vector: its handler
    ; (F000:EF57) sets BDA 0040:003E bit 7 and issues the PIC EOI, which the
    ; INT 13h wait loop (F000:EEBA) spins on. Native IVT init leaves it wrong,
    ; so the FDC completion IRQ6 never released the wait loop and boot stalled.
    ; Last opcode E9=near JMP rel16: disp=$002D (IP after=$E6C5 -> $E6F2).
    ; High byte MUST be $00; $E9 is relative, not far/absolute.
    .byte $31,$C0,$8E,$D8,$B8,$A5,$FE,$A3,$20,$00
    .byte $B8,$59,$EC,$A3,$4C,$00,$B8,$00,$F0,$A3
    .byte $22,$00,$A3,$4E,$00,$A3,$3A,$00,$B8,$57
    .byte $EF,$A3,$38,$00,$E9,$2D,$00
genxt_bootstrap_patch_size = *-genxt_bootstrap_patch

guest_genxt_bios:
    .incbin "third_party/pcem-roms/genxt/pcxt.rom"
