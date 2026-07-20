.setcpu "6502"

; Generated from the linked diagnostic payload by generate_cartridge_include.py.
.include "cartridge_payload.inc"

D016 = $D016
MAGIC_DESK_BANK = $DE00

COPY_SOURCE = $FB
COPY_DEST   = $FD
TRAMPOLINE_RAM = $0200

.segment "ROM"

; Standard C64 autostart header at $8000.
    .word cold_start
    .word warm_start
    .byte $C3, $C2, $CD, $38, $30       ; "CBM80"

cold_start:
warm_start:
    sei
    ldx #$FF
    txs
    stx D016
    jsr $FDA3                           ; initialize CIA/I/O
    jsr $FD50                           ; initialize RAM
    jsr $FD15                           ; restore KERNAL vectors
    jsr $FF5B                           ; initialize screen

    lda #<PAYLOAD_ROM_ADDRESS
    sta COPY_SOURCE
    lda #>PAYLOAD_ROM_ADDRESS
    sta COPY_SOURCE+1
    lda #<PAYLOAD_LOAD_ADDRESS
    sta COPY_DEST
    lda #>PAYLOAD_LOAD_ADDRESS
    sta COPY_DEST+1

    ldx #>PAYLOAD_SIZE
    beq @copy_tail
@copy_page:
    ldy #$00
@copy_page_byte:
    lda (COPY_SOURCE),y
    sta (COPY_DEST),y
    iny
    bne @copy_page_byte
    inc COPY_SOURCE+1
    inc COPY_DEST+1
    dex
    bne @copy_page

@copy_tail:
    ldy #$00
@copy_tail_byte:
    cpy #<PAYLOAD_SIZE
    beq @payload_copied
    lda (COPY_SOURCE),y
    sta (COPY_DEST),y
    iny
    bne @copy_tail_byte

@payload_copied:
    ; ld65 BSS is not stored in the PRG. Clear it before entering assembly code
    ; so cache-valid flags and diagnostic state are deterministic.
    lda #<PAYLOAD_BSS_START
    sta COPY_DEST
    lda #>PAYLOAD_BSS_START
    sta COPY_DEST+1
    lda #$00
    ldx #>PAYLOAD_BSS_SIZE
    beq @clear_tail
@clear_page:
    ldy #$00
@clear_page_byte:
    sta (COPY_DEST),y
    iny
    bne @clear_page_byte
    inc COPY_DEST+1
    dex
    bne @clear_page

@clear_tail:
    ldy #$00
@clear_tail_byte:
    cpy #<PAYLOAD_BSS_SIZE
    beq @bss_cleared
    sta (COPY_DEST),y
    iny
    bne @clear_tail_byte

@bss_cleared:
    ; Disabling Magic Desk replaces ROM at $8000 immediately, so execute the
    ; final write and jump from a short RAM trampoline.
    ldy #$00
@copy_trampoline:
    lda trampoline,y
    sta TRAMPOLINE_RAM,y
    iny
    cpy #trampoline_end-trampoline
    bne @copy_trampoline
    jmp TRAMPOLINE_RAM

trampoline:
    lda #$80
    sta MAGIC_DESK_BANK                 ; bit 7 disables GAME/EXROM
    cli
    jsr PAYLOAD_ENTRY
@halt:
    ; The diagnostic is also a normal PRG and therefore returns with RTS.
    ; A cartridge has no BASIC caller to return to, so keep its final screen
    ; visible instead of falling through an undefined reset stack frame.
    jmp TRAMPOLINE_RAM + (@halt - trampoline)
trampoline_end:

.assert * <= PAYLOAD_ROM_ADDRESS, error, "cartridge bootstrap exceeds reserved space"
